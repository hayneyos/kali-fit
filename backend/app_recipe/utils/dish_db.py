import json

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
from PIL import Image
import base64
import io
import re
from psycopg2 import pool


class DishDatabase:
    _instance = None
    _pool = None

    def __new__(cls, db_url=None, default_prompt=None):
        if cls._instance is None:
            cls._instance = super(DishDatabase, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance


    def __init__(self, db_url=None, default_prompt=None):
        if self._initialized:
            return

        self.db_url = db_url or os.getenv('POSTGRES_DB_URL')
        self.default_prompt = default_prompt
        
        # Initialize connection pool
        if self._pool is None:
            try:
                # Parse connection string to get individual parameters
                conn_params = self._parse_connection_string(self.db_url)
                self._pool = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    **conn_params
                )
            except Exception as e:
                print(f"Error initializing connection pool: {str(e)}")
                self._pool = None

        # Create tables
        self._create_tables()
        self._initialized = True

    def _parse_connection_string(self, conn_string):
        """Parse PostgreSQL connection string into parameters"""
        if not conn_string:
            return {
                "dbname": os.getenv("PG_DB", "mydb"),
                "user": os.getenv("PG_USER", "admin"),
                "password": os.getenv("PG_PASSWORD", "road0247!~Sense"),
                "host": os.getenv("PG_HOST", "localhost"),
                "port": os.getenv("PG_PORT", "5432")
            }

        # Parse postgresql://user:password@host:port/dbname format
        pattern = r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
        match = re.match(pattern, conn_string)
        if match:
            user, password, host, port, dbname = match.groups()
            return {
                "dbname": dbname,
                "user": user,
                "password": password,
                "host": host,
                "port": port
            }
        return {}

    def _get_connection(self):
        """Get a connection from the pool"""
        if not self._pool:
            raise Exception("Database connection pool not initialized")
        return self._pool.getconn()

    def _return_connection(self, conn):
        """Return a connection to the pool"""
        if self._pool:
            self._pool.putconn(conn)

    def _drop_tables(self):
        """Drop existing tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DROP TABLE IF EXISTS dishes CASCADE;')
            cursor.execute('DROP TABLE IF EXISTS prompts CASCADE;')
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create prompts table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS prompts (
                id SERIAL PRIMARY KEY,
                prompt TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')

            cursor.execute('''
           CREATE TABLE IF NOT EXISTS dishes (
                id SERIAL PRIMARY KEY,
                image_path TEXT,
                filename TEXT,
                dish_name TEXT,
                ingredients TEXT,
                model_size TEXT,
                environment TEXT DEFAULT 'prod',
                version TEXT DEFAULT 'v1',
                prompt_id INTEGER REFERENCES prompts(id),
                prediction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified BOOLEAN DEFAULT FALSE,
                output_json JSONB DEFAULT '{}'::jsonb,
                response_model_result JSONB DEFAULT '{}'::jsonb,
                response_model_meta JSONB DEFAULT '{}'::jsonb,
                running_time FLOAT,
                image_details JSONB DEFAULT '{}'::jsonb,
                UNIQUE (image_path, environment, version, filename, prompt_id)
            );
            ''')

            # Grant permissions to all users
            cursor.execute('GRANT ALL PRIVILEGES ON TABLE prompts TO PUBLIC;')
            cursor.execute('GRANT ALL PRIVILEGES ON TABLE dishes TO PUBLIC;')
            cursor.execute('GRANT USAGE, SELECT ON SEQUENCE prompts_id_seq TO PUBLIC;')
            cursor.execute('GRANT USAGE, SELECT ON SEQUENCE dishes_id_seq TO PUBLIC;')

            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_or_create_prompt(self, prompt_text):
        """Get prompt ID if exists, create new if doesn't exist"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Try to get existing prompt
            cursor.execute('SELECT id FROM prompts WHERE prompt = %s', (prompt_text,))
            result = cursor.fetchone()

            if result:
                return result[0]  # Return existing prompt ID

            # Create new prompt
            cursor.execute('''
                INSERT INTO prompts (prompt) 
                VALUES (%s) 
                ON CONFLICT (prompt) DO UPDATE 
                SET prompt = EXCLUDED.prompt 
                RETURNING id
            ''', (prompt_text,))
            new_id = cursor.fetchone()[0]
            conn.commit()
            return new_id

        except Exception as e:
            print(f"Error in get_or_create_prompt: {str(e)}")
            # If there's an error, try to get the prompt again
            try:
                cursor.execute('SELECT id FROM prompts WHERE prompt = %s', (prompt_text,))
                result = cursor.fetchone()
                if result:
                    return result[0]
                return None
            except Exception as e2:
                print(f"Error in retry get prompt: {str(e2)}")
                return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_prompt_by_id(self, prompt_id):
        """Get prompt text by ID"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT prompt FROM prompts WHERE id = %s', (prompt_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def add_dish(self, image_path, filename, dish_name, ingredients, model_size, environment='prod', version='v1',
                 verified=False, prediction_time=None):
        """Add a new dish entry to the database"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if prediction_time is None:
                prediction_time = datetime.utcnow()

            cursor.execute('''
                INSERT INTO dishes (image_path, filename, dish_name, ingredients, model_size, environment, version, verified, prediction_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (image_path, environment, version, filename)
                DO UPDATE SET 
                    dish_name = EXCLUDED.dish_name,
                    ingredients = EXCLUDED.ingredients,
                    model_size = EXCLUDED.model_size,
                    verified = EXCLUDED.verified,
                    prediction_time = EXCLUDED.prediction_time
            ''', (
                image_path, filename, dish_name, ingredients, model_size, environment, version, verified,
                prediction_time))

            conn.commit()
            return True
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def update_dish_info(self, filename, dish_name, ingredients, verified=True):
        """Update dish information with verified data"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE dishes 
            SET dish_name = %s, ingredients = %s, verified = %s
            WHERE filename = %s
            ''', (dish_name, ingredients, verified, filename))

            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_dish_by_image(self, image_path):
        """Retrieve dish information by image path"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute('SELECT * FROM dishes WHERE image_path = %s', (image_path,))
            result = cursor.fetchone()

            return result
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def _get_image_details(self, image_path_or_data, is_base64=False):
        """Get image metadata using PIL from either file path or base64 data"""
        try:
            if is_base64:
                # Handle base64 encoded image
                image_data = base64.b64decode(image_path_or_data)
                img = Image.open(io.BytesIO(image_data))
            else:
                # Handle file path
                img = Image.open(image_path_or_data)

            # Get basic image information
            details = {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
                'size_bytes': len(image_data) if is_base64 else os.path.getsize(image_path_or_data),
                'dpi': img.info.get('dpi', None),
                'compression': img.info.get('compression', None),
                'progressive': img.info.get('progressive', False),
                'transparency': img.info.get('transparency', None),
                'aspect_ratio': round(img.width / img.height, 3),
                'orientation': 'landscape' if img.width > img.height else 'portrait' if img.height > img.width else 'square',
                'color_depth': self._get_color_depth(img.mode),
                'is_grayscale': img.mode in ('L', '1'),
                'is_rgba': img.mode == 'RGBA',
                'is_indexed': img.mode == 'P',
                'is_animated': getattr(img, 'is_animated', False),
                'frames': getattr(img, 'n_frames', 1)
            }

            # Add EXIF data if available
            if hasattr(img, '_getexif') and img._getexif():
                details['exif'] = {
                    'make': img._getexif().get(271, None),  # Make
                    'model': img._getexif().get(272, None),  # Model
                    'datetime': img._getexif().get(306, None),  # DateTime
                    'exposure_time': img._getexif().get(33434, None),  # ExposureTime
                    'f_number': img._getexif().get(33437, None),  # FNumber
                    'iso': img._getexif().get(34855, None),  # ISOSpeedRatings
                    'focal_length': img._getexif().get(37386, None),  # FocalLength
                }

            return details
        except Exception as e:
            print(f"Error getting image details: {str(e)}")
            return {}

    def _get_color_depth(self, mode):
        """Get color depth based on image mode"""
        depth_map = {
            '1': 1,  # Binary
            'L': 8,  # Grayscale
            'P': 8,  # Palette
            'RGB': 24,  # RGB
            'RGBA': 32,  # RGBA
            'CMYK': 32,  # CMYK
            'YCbCr': 24,  # YCbCr
            'LAB': 24,  # LAB
            'HSV': 24,  # HSV
            'I': 32,  # Integer
            'F': 32,  # Float
        }
        return depth_map.get(mode, 0)

    def update_image_details(self, image_path=None, base64_data=None):
        """Update image details for a specific image or all images in the database"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if image_path:
                # Update single image
                image_details = self._get_image_details(image_path)
                cursor.execute('''
                    UPDATE dishes 
                    SET image_details = %s 
                    WHERE image_path = %s
                ''', (json.dumps(image_details), image_path))
            elif base64_data:
                # Update using base64 data
                image_details = self._get_image_details(base64_data, is_base64=True)
                cursor.execute('''
                    UPDATE dishes 
                    SET image_details = %s 
                    WHERE image_path = %s
                ''', (json.dumps(image_details), image_path))
            else:
                # Update all images
                cursor.execute(
                    'SELECT DISTINCT image_path FROM dishes WHERE image_details IS NULL OR image_details = \'{}\'')
                image_paths = cursor.fetchall()

                for (path,) in image_paths:
                    if os.path.exists(path):
                        image_details = self._get_image_details(path)
                        cursor.execute('''
                            UPDATE dishes 
                            SET image_details = %s 
                            WHERE image_path = %s
                        ''', (json.dumps(image_details), path))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating image details: {str(e)}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_image_details(self, image_path):
        """Get stored image details for a specific image"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute('''
                SELECT image_details 
                FROM dishes 
                WHERE image_path = %s 
                LIMIT 1
            ''', (image_path,))

            result = cursor.fetchone()
            return result['image_details'] if result else None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _extract_image_from_body(self, body):
        """Extract image data from the prompt body"""
        try:
            # Check if body contains messages
            if not isinstance(body, dict) or 'messages' not in body:
                return None, None

            # Look for image data in messages
            for message in body['messages']:
                if not isinstance(message, dict) or 'content' not in message:
                    continue

                content = message['content']
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'image_url':
                            image_url = item.get('image_url', {}).get('url', '')
                            if image_url.startswith('data:image'):
                                # Extract base64 data
                                base64_data = image_url.split(',')[1]
                                return base64_data, 'base64'
                            elif image_url.startswith('file://'):
                                # Extract file path
                                file_path = image_url[7:]  # Remove 'file://'
                                return file_path, 'file'
                            else:
                                # Regular URL
                                return image_url, 'url'

            return None, None
        except Exception as e:
            print(f"Error extracting image from body: {str(e)}")
            return None, None

    def _get_image_details_from_body(self, body):
        """Get image details from the prompt body"""
        image_data, data_type = self._extract_image_from_body(body)
        if not image_data:
            return {}

        try:
            if data_type == 'base64':
                return self._get_image_details(image_data, is_base64=True)
            elif data_type == 'file':
                return self._get_image_details(image_data)
            elif data_type == 'url':
                # For URLs, we'll just store the URL information
                return {
                    'source_type': 'url',
                    'url': image_data
                }
            return {}
        except Exception as e:
            print(f"Error getting image details from body: {str(e)}")
            return {}

    def save_dish_from_openai(self, image_path, filename, model_size, output_json, environment='prod', version='v1',
                              verified=False, prompt_id=None, response_model_result=None, response_model_meta=None,
                              running_time=None, body=None, image_details=None):
        """Insert or update a dish record from OpenAI result"""
        conn = None
        cursor = None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # If prompt_id is None, get or create it
            if prompt_id is None:
                prompt_id = self.get_or_create_prompt(self.default_prompt)
            else:
                # Verify prompt exists
                prompt_text = self.get_prompt_by_id(prompt_id)
                if prompt_text is None:
                    # If prompt doesn't exist, create it
                    prompt_id = self.get_or_create_prompt(self.default_prompt)

            # Extract fields from output_json (which now contains the parsed dish data)
            dish_name = output_json.get('meal_name', '')
            ingredients = output_json.get('ingredients', [])
            ingredients_str = ", ".join(ingredients) if isinstance(ingredients, list) else str(ingredients)

            prediction_time = datetime.utcnow()  # Save prediction time

            # Get image details from parameter or extract from body
            if image_details is None:
                if body:
                    image_details = self._get_image_details_from_body(body)
                else:
                    image_details = self._get_image_details(image_path)

            # Insert or Update dish
            cursor.execute('''
                INSERT INTO dishes (
                    image_path, filename, model_size, dish_name, ingredients, 
                    output_json, response_model_result, response_model_meta,
                    environment, version, prediction_time, verified, prompt_id,
                    running_time, image_details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (image_path, environment, version, filename, prompt_id)
                DO UPDATE SET 
                    model_size = EXCLUDED.model_size,
                    dish_name = EXCLUDED.dish_name,
                    ingredients = EXCLUDED.ingredients,
                    output_json = EXCLUDED.output_json,
                    response_model_result = EXCLUDED.response_model_result,
                    response_model_meta = EXCLUDED.response_model_meta,
                    prediction_time = EXCLUDED.prediction_time,
                    verified = EXCLUDED.verified,
                    running_time = EXCLUDED.running_time,
                    image_details = EXCLUDED.image_details
            ''', (
                image_path,
                filename,
                model_size,
                dish_name,
                ingredients_str,
                json.dumps(output_json),
                json.dumps(response_model_result) if response_model_result else None,
                json.dumps(response_model_meta) if response_model_meta else None,
                environment,
                version,
                prediction_time,
                verified,
                prompt_id,
                running_time,
                json.dumps(image_details)
            ))

            conn.commit()
            return True

        except Exception as e:
            print(f"Error saving dish: {str(e)}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_all_dishes(self):
        """Retrieve all dishes from the database"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute('SELECT * FROM dishes')
            results = cursor.fetchall()

            return results
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_dishes_by_imagename(self, image):
        """Get dishes that contain any of the specified ingredients"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # safe_filename = "".join(c if c.isalnum() else "_" for c in image.lower()) + ".jpg"

            # Build the query with multiple LIKE conditions
            query = '''
                  SELECT * FROM dishes 
                  WHERE image_path LIKE (%s)
                  ORDER BY dish_name
              '''

            cursor.execute(query, (image,))
            results = cursor.fetchall()

            return results
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def get_dishes_by_ingredients(self, ingredients_list):
        """Get dishes that contain any of the specified ingredients"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Create a pattern for each ingredient to match
            patterns = [f'%{ingredient}%' for ingredient in ingredients_list]
            
            # Build the query with multiple LIKE conditions
            query = '''
                SELECT * FROM dishes 
                WHERE ingredients ILIKE ANY(%s)
                ORDER BY dish_name
            '''
            
            cursor.execute(query, (patterns,))
            results = cursor.fetchall()
            
            return results
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)

    def compare_ingredients(self, csv_ingredients, db_ingredients):
        """Compare ingredients between CSV and database records"""
        # Convert both to sets of lowercase strings for case-insensitive comparison
        csv_set = {ing.strip().lower() for ing in csv_ingredients.split(',') if ing.strip()}
        db_set = {ing.strip().lower() for ing in db_ingredients.split(',') if ing.strip()}
        
        # Find matches and differences
        matches = csv_set.intersection(db_set)
        only_in_csv = csv_set - db_set
        only_in_db = db_set - csv_set
        
        return {
            'matches': list(matches),
            'only_in_csv': list(only_in_csv),
            'only_in_db': list(only_in_db),
            'match_percentage': len(matches) / len(csv_set) * 100 if csv_set else 0
        }

    def dish_exists(self, image_path, model_size, environment="prod", version="v1", prompt_id=None):
        """Check if a dish already exists in the database with the same version, model, environment and prompt"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM dishes 
                WHERE image_path = %s 
                AND model_size = %s 
                AND environment = %s 
                AND version = %s
                AND prompt_id = %s
            ''', (image_path, model_size, environment, version, prompt_id))

            result = cursor.fetchone()
            return result is not None
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._return_connection(conn)
