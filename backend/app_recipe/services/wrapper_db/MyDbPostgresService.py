import logging
import os
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import date
from dotenv import load_dotenv
from psycopg2 import pool
from psycopg2.extras import Json

from backend.app_recipe.utils.logger import LoggerConfig, get_logger

load_dotenv()


# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('recipe_routes')


class MyDbPostgresService:
    def __init__(self):
        try:
            self.pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=3,
                user=os.getenv("PG_USER", "admin"),
                password=os.getenv("PG_PASSWORD", "road0247!~Sense"),
                host=os.getenv("PG_HOST", "localhost"),
                port=os.getenv("PG_PORT", "5432"),
                database=os.getenv("PG_DB", "mydb")
            )
            logger.info("✅ PostgreSQL connection pool initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize DB pool: {e}")
            self.pool = None

    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[tuple]:
        if not self.pool:
            logger.error("DB pool not available")
            return None
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Fetch failed: {e}")
            return None
        finally:
            self.pool.putconn(conn)

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query and return the results as a list of dictionaries."""
        if not self.pool:
            logger.error("DB pool not available")
            return []
        conn = self.pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    if cur.description:
                        columns = [desc[0] for desc in cur.description]
                        return [dict(zip(columns, row)) for row in cur.fetchall()]
                    return []
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            return []
        finally:
            self.pool.putconn(conn)

    def execute_update(self, query: str, params: Optional[tuple] = None) -> bool:
        """Execute an update/insert/delete query and return success status."""
        if not self.pool:
            logger.error("DB pool not available")
            return False
        conn = self.pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Update failed: {e}")
            return False
        finally:
            self.pool.putconn(conn)

    # ---------- Table Management ----------
    def initialize_tables(self) -> bool:
        """Initialize all required tables"""
        try:
            self.create_users_table()
            self.create_meals_table()
            self.create_user_profiles_table()
            self.create_recipes_table()
            self.create_products_table()
            self.create_openai_requests_table()
            self.create_events_table()
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize tables: {e}")
            return False

    def create_openai_requests_table(self) -> bool:
        return self.execute_update("""
            CREATE TABLE IF NOT EXISTS openai_requests (
                id SERIAL PRIMARY KEY,
                email TEXT,
                device_id TEXT,
                ip_address TEXT,
                request_data JSONB,
                response_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def create_users_table(self) -> bool:
        return self.execute_update("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                device_id TEXT,
                ip_address TEXT,
                subscription_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tokens_used INTEGER DEFAULT 0,
                total_requests INTEGER DEFAULT 0,
                subscription_type TEXT DEFAULT 'free',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def create_meals_table(self) -> bool:
        return self.execute_update("""
            CREATE TABLE IF NOT EXISTS meals (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                date DATE,
                meal_type TEXT,
                product_name TEXT,
                manufacturer TEXT,
                calories FLOAT,
                protein FLOAT,
                fat FLOAT,
                carbs FLOAT,
                weight_grams FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def create_user_profiles_table(self) -> bool:
        return self.execute_update("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                age INTEGER,
                gender TEXT,
                weight FLOAT,
                goal TEXT,
                preferences TEXT[]
            )
        """)

    def truncate_openai_requests(self):
        self.execute_query("TRUNCATE TABLE openai_requests")

    def create_recipes_table(self) -> bool:
        return self.execute_update("""
            CREATE TABLE IF NOT EXISTS recipes (
                id SERIAL PRIMARY KEY,
                name TEXT,
                category TEXT,
                calories FLOAT,
                protein FLOAT,
                fat FLOAT,
                carbs FLOAT
            )
        """)

    def create_products_table(self) -> bool:
        return self.execute_update("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT,
                manufacturer TEXT,
                calories FLOAT,
                protein FLOAT,
                fat FLOAT,
                carbs FLOAT,
                image_url TEXT
            )
        """)

    def create_events_table(self) -> bool:
        return self.execute_update("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                user_id TEXT,
                device_id TEXT,
                ip_address TEXT,
                event_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # ---------- Product Operations ----------
    def create_product(self, name: str, manufacturer: str, calories: float, 
                      protein: float, fat: float, carbs: float, image_url: Optional[str] = None) -> bool:
        return self.execute_update("""
            INSERT INTO products (name, manufacturer, calories, protein, fat, carbs, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (name, manufacturer, calories, protein, fat, carbs, image_url))

    def get_products(self) -> List[Dict[str, Any]]:
        results = self.execute_query("SELECT * FROM products")
        return results

    def get_products_count(
        self,
        search_term: Optional[str] = None,
        manufacturer: Optional[str] = None,
        min_calories: Optional[float] = None,
        max_calories: Optional[float] = None
    ) -> int:
        """Get total count of products matching search criteria."""
        try:
            query = "SELECT COUNT(*) FROM products WHERE 1=1"
            params = []
            
            if search_term:
                query += " AND (name ILIKE %s OR manufacturer ILIKE %s)"
                params.extend([f"%{search_term}%", f"%{search_term}%"])
            
            if manufacturer:
                query += " AND manufacturer ILIKE %s"
                params.append(f"%{manufacturer}%")
            
            if min_calories is not None:
                query += " AND calories >= %s"
                params.append(min_calories)
            
            if max_calories is not None:
                query += " AND calories <= %s"
                params.append(max_calories)
            
            result = self.fetch_one(query, params)
            return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Error getting products count: {e}")
            return 0

    def search_products(
        self,
        search_term: Optional[str] = None,
        manufacturer: Optional[str] = None,
        min_calories: Optional[float] = None,
        max_calories: Optional[float] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Search products with pagination."""
        try:
            query = "SELECT * FROM products WHERE 1=1"
            params = []
            
            if search_term:
                query += " AND (name ILIKE %s OR manufacturer ILIKE %s)"
                params.extend([f"%{search_term}%", f"%{search_term}%"])
            
            if manufacturer:
                query += " AND manufacturer ILIKE %s"
                params.append(f"%{manufacturer}%")
            
            if min_calories is not None:
                query += " AND calories >= %s"
                params.append(min_calories)
            
            if max_calories is not None:
                query += " AND calories <= %s"
                params.append(max_calories)
            
            # Add sorting
            valid_sort_fields = ["name", "calories", "protein"]
            sort_by = sort_by if sort_by in valid_sort_fields else "name"
            sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
            query += f" ORDER BY {sort_by} {sort_order}"
            
            # Add pagination
            offset = (page - 1) * page_size
            query += " LIMIT %s OFFSET %s"
            params.extend([page_size, offset])
            
            return self.execute_query(query, params)
        except Exception as e:
            self.logger.error(f"Error searching products: {e}")
            return []

    # ---------- Meal Operations ----------
    def create_meal(self, user_id: str, date: date, meal_type: str, product_name: str,
                   manufacturer: str, calories: float, protein: float, fat: float,
                   carbs: float, weight_grams: float) -> bool:
        return self.execute_update("""
            INSERT INTO meals (user_id, date, meal_type, product_name, manufacturer, 
                             calories, protein, fat, carbs, weight_grams)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, date, meal_type, product_name, manufacturer, calories, protein, fat, carbs, weight_grams))

    def get_user_meals(self, user_id: str, meal_date: Optional[date] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM meals WHERE user_id = %s"
        params = [user_id]
        
        if meal_date:
            query += " AND date = %s"
            params.append(meal_date)
            
        result = self.fetch_one(query, tuple(params))
        if not result:
            return []
        return [dict(zip(['id', 'user_id', 'date', 'meal_type', 'product_name', 'manufacturer', 
                         'calories', 'protein', 'fat', 'carbs', 'weight_grams', 'created_at'], result))]

    def get_user_meals_count(
        self,
        user_id: str,
        search_term: Optional[str] = None,
        meal_type: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        min_calories: Optional[float] = None,
        max_calories: Optional[float] = None
    ) -> int:
        """Get total count of user meals matching search criteria."""
        try:
            query = "SELECT COUNT(*) FROM meals WHERE user_id = %s"
            params = [user_id]
            
            if search_term:
                query += " AND (product_name ILIKE %s OR product_manufacturer ILIKE %s)"
                params.extend([f"%{search_term}%", f"%{search_term}%"])
            
            if meal_type:
                query += " AND meal_type = %s"
                params.append(meal_type)
            
            if date_from:
                query += " AND date >= %s"
                params.append(date_from)
            
            if date_to:
                query += " AND date <= %s"
                params.append(date_to)
            
            if min_calories is not None:
                query += " AND calories >= %s"
                params.append(min_calories)
            
            if max_calories is not None:
                query += " AND calories <= %s"
                params.append(max_calories)
            
            result = self.fetch_one(query, params)
            return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Error getting user meals count: {e}")
            return 0

    def search_user_meals(
        self,
        user_id: str,
        search_term: Optional[str] = None,
        meal_type: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        min_calories: Optional[float] = None,
        max_calories: Optional[float] = None,
        sort_by: str = "date",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Search user meals with pagination."""
        try:
            query = "SELECT * FROM meals WHERE user_id = %s"
            params = [user_id]
            
            if search_term:
                query += " AND (product_name ILIKE %s OR product_manufacturer ILIKE %s)"
                params.extend([f"%{search_term}%", f"%{search_term}%"])
            
            if meal_type:
                query += " AND meal_type = %s"
                params.append(meal_type)
            
            if date_from:
                query += " AND date >= %s"
                params.append(date_from)
            
            if date_to:
                query += " AND date <= %s"
                params.append(date_to)
            
            if min_calories is not None:
                query += " AND calories >= %s"
                params.append(min_calories)
            
            if max_calories is not None:
                query += " AND calories <= %s"
                params.append(max_calories)
            
            # Add sorting
            valid_sort_fields = ["date", "calories", "meal_type"]
            sort_by = sort_by if sort_by in valid_sort_fields else "date"
            sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
            query += f" ORDER BY {sort_by} {sort_order}"
            
            # Add pagination
            offset = (page - 1) * page_size
            query += " LIMIT %s OFFSET %s"
            params.extend([page_size, offset])
            
            return self.execute_query(query, params)
        except Exception as e:
            self.logger.error(f"Error searching user meals: {e}")
            return []

    # ---------- User Profile Operations ----------
    def create_user_profile(self, user_id: str, age: int, gender: str, weight: float,
                          goal: str, preferences: List[str]) -> bool:
        return self.execute_update("""
            INSERT INTO user_profiles (user_id, age, gender, weight, goal, preferences)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET age = EXCLUDED.age,
                gender = EXCLUDED.gender,
                weight = EXCLUDED.weight,
                goal = EXCLUDED.goal,
                preferences = EXCLUDED.preferences
        """, (user_id, age, gender, weight, goal, preferences))

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        result = self.fetch_one("SELECT * FROM user_profiles WHERE user_id = %s", (user_id,))
        if not result:
            return None
        return dict(zip(['user_id', 'age', 'gender', 'weight', 'goal', 'preferences'], result))

    # ---------- Recipe Operations ----------
    def create_recipe(self, name: str, category: str, calories: float,
                     protein: float, fat: float, carbs: float) -> bool:
        return self.execute_update("""
            INSERT INTO recipes (name, category, calories, protein, fat, carbs)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, category, calories, protein, fat, carbs))

    def get_recipes(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM recipes"
        params = []
        
        if category:
            query += " WHERE category = %s"
            params.append(category)
            
        result = self.fetch_one(query, tuple(params) if params else None)
        if not result:
            return []
        return [dict(zip(['id', 'name', 'category', 'calories', 'protein', 'fat', 'carbs'], row)) 
                for row in result]

    def get_recipes_count(
        self,
        search_term: Optional[str] = None,
        category: Optional[str] = None,
        min_calories: Optional[float] = None,
        max_calories: Optional[float] = None,
        min_protein: Optional[float] = None,
        max_protein: Optional[float] = None
    ) -> int:
        """Get total count of recipes matching search criteria."""
        try:
            query = "SELECT COUNT(*) FROM recipes WHERE 1=1"
            params = []
            
            if search_term:
                query += " AND name ILIKE %s"
                params.append(f"%{search_term}%")
            
            if category:
                query += " AND category = %s"
                params.append(category)
            
            if min_calories is not None:
                query += " AND calories >= %s"
                params.append(min_calories)
            
            if max_calories is not None:
                query += " AND calories <= %s"
                params.append(max_calories)
            
            if min_protein is not None:
                query += " AND protein >= %s"
                params.append(min_protein)
            
            if max_protein is not None:
                query += " AND protein <= %s"
                params.append(max_protein)
            
            result = self.fetch_one(query, params)
            return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Error getting recipes count: {e}")
            return 0

    def search_recipes(
        self,
        search_term: Optional[str] = None,
        category: Optional[str] = None,
        min_calories: Optional[float] = None,
        max_calories: Optional[float] = None,
        min_protein: Optional[float] = None,
        max_protein: Optional[float] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Search recipes with pagination."""
        try:
            query = "SELECT * FROM recipes WHERE 1=1"
            params = []
            
            if search_term:
                query += " AND name ILIKE %s"
                params.append(f"%{search_term}%")
            
            if category:
                query += " AND category = %s"
                params.append(category)
            
            if min_calories is not None:
                query += " AND calories >= %s"
                params.append(min_calories)
            
            if max_calories is not None:
                query += " AND calories <= %s"
                params.append(max_calories)
            
            if min_protein is not None:
                query += " AND protein >= %s"
                params.append(min_protein)
            
            if max_protein is not None:
                query += " AND protein <= %s"
                params.append(max_protein)
            
            # Add sorting
            valid_sort_fields = ["name", "calories", "protein"]
            sort_by = sort_by if sort_by in valid_sort_fields else "name"
            sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
            query += f" ORDER BY {sort_by} {sort_order}"
            
            # Add pagination
            offset = (page - 1) * page_size
            query += " LIMIT %s OFFSET %s"
            params.extend([page_size, offset])
            
            return self.execute_query(query, params)
        except Exception as e:
            self.logger.error(f"Error searching recipes: {e}")
            return []

    # ---------- OpenAI Logging Operations ----------
    def insert_openai_log(self, email: str, device_id: str, ip_address: str,
                         request_data: Dict[str, Any], response_data: Dict[str, Any]) -> bool:
        return self.execute_update("""
            INSERT INTO openai_requests (email, device_id, ip_address, request_data, response_data)
            VALUES (%s, %s, %s, %s, %s)
        """, (email, device_id, ip_address, json.dumps(request_data), json.dumps(response_data)))

    def get_openai_logs(self, email: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM openai_requests"
        params = []
        
        if email:
            query += " WHERE email = %s"
            params.append(email)
            
        result = self.fetch_one(query, tuple(params) if params else None)
        if not result:
            return []
        return [dict(zip(['id', 'email', 'device_id', 'ip_address', 'request_data', 
                         'response_data', 'created_at'], row)) 
                for row in result]

    def get_openai_logs_count(
        self,
        email: Optional[str] = None,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> int:
        """Get total count of OpenAI logs matching search criteria."""
        try:
            query = "SELECT COUNT(*) FROM openai_requests WHERE 1=1"
            params = []
            
            if email:
                query += " AND email = %s"
                params.append(email)
            
            if device_id:
                query += " AND device_id = %s"
                params.append(device_id)
            
            if ip_address:
                query += " AND ip_address = %s"
                params.append(ip_address)
            
            if date_from:
                query += " AND created_at >= %s"
                params.append(date_from)
            
            if date_to:
                query += " AND created_at <= %s"
                params.append(date_to)
            
            result = self.fetch_one(query, params)
            return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Error getting OpenAI logs count: {e}")
            return 0

    def search_openai_logs(
        self,
        email: Optional[str] = None,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Search OpenAI logs with pagination."""
        try:
            query = "SELECT * FROM openai_requests WHERE 1=1"
            params = []
            
            if email:
                query += " AND email = %s"
                params.append(email)
            
            if device_id:
                query += " AND device_id = %s"
                params.append(device_id)
            
            if ip_address:
                query += " AND ip_address = %s"
                params.append(ip_address)
            
            if date_from:
                query += " AND created_at >= %s"
                params.append(date_from)
            
            if date_to:
                query += " AND created_at <= %s"
                params.append(date_to)
            
            # Add sorting
            valid_sort_fields = ["created_at", "email"]
            sort_by = sort_by if sort_by in valid_sort_fields else "created_at"
            sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
            query += f" ORDER BY {sort_by} {sort_order}"
            
            # Add pagination
            offset = (page - 1) * page_size
            query += " LIMIT %s OFFSET %s"
            params.extend([page_size, offset])
            
            return self.execute_query(query, params)
        except Exception as e:
            self.logger.error(f"Error searching OpenAI logs: {e}")
            return []

    # ---------- Truncate Tables ----------

    def truncate_all_tables(self):
        tables = ["openai_requests", "users", "meals", "user_profiles", "recipes", "products"]
        for table in tables:
            self.execute_update(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")


    def upsert_user(self, email, device_id, ip_address):
        self.execute_query("""
            INSERT INTO users (email, device_id, ip_address, last_used, total_requests)
            VALUES (%s, %s, %s, NOW(), 1)
            ON CONFLICT (email) DO UPDATE
            SET device_id = EXCLUDED.device_id,
                ip_address = EXCLUDED.ip_address,
                last_used = NOW(),
                total_requests = users.total_requests + 1
        """, (email, device_id, ip_address))

