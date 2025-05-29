FROM python:3.10-bullseye

# התקנת כלים בסיסיים
RUN apt-get update && apt-get install -y procps

# הגדרת ספריית עבודה
WORKDIR /usr/src/backend

# יצירת מבנה תיקיות
RUN mkdir -p /usr/src/backend/app_recipe/static

# העתקת קובץ requirements וקובץ הסביבה
COPY app_recipe/requirements.txt /usr/src/backend/app_recipe/
RUN pip install --no-cache-dir -r /usr/src/backend/app_recipe/requirements.txt

# הגדרת משתני סביבה
ENV PYTHONPATH=/usr/src/backend \
    RUNNING_IN_DOCKER=true \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8093 \
    REDIS_HOST=localhost \
    REDIS_PORT=6379 \
    REDIS_DB=0 \
    REDIS_PASSWORD=your_strong_password \
    MONGO_HOST=134.199.235.88 \
    MONGO_PORT=27017 \
    MONGO_INITDB_ROOT_USERNAME=admin \
    MONGO_INITDB_ROOT_PASSWORD=road0247!~Sense!@#$ \
    MONGO_DB_NAME=mydatabase \
    MONGO_URI=mongodb://admin:road0247%21~Sense%21%40%23%24@134.199.235.88:27017/mydatabase?authSource=admin

# Create .env file with the same environment variables
RUN echo "SERVER_HOST=${SERVER_HOST}\n\
SERVER_PORT=${SERVER_PORT}\n\
LOG_DIR=logs\n\
DATA_DIR=data\n\
MY_SERVER_IP=localhost\n\
MY_SERVER_NAME=localhost\n\
RUNNING_IN_DOCKER=${RUNNING_IN_DOCKER}\n\
USE_API_PREFIX=false\n\
MONGO_HOST=${MONGO_HOST}\n\
MONGO_PORT=${MONGO_PORT}\n\
MONGO_INITDB_ROOT_USERNAME=${MONGO_INITDB_ROOT_USERNAME}\n\
MONGO_INITDB_ROOT_PASSWORD=${MONGO_INITDB_ROOT_PASSWORD}\n\
MONGO_DB_NAME=${MONGO_DB_NAME}\n\
MONGO_URI=${MONGO_URI}\n\
REDIS_HOST=${REDIS_HOST}\n\
REDIS_PORT=${REDIS_PORT}\n\
REDIS_DB=${REDIS_DB}\n\
REDIS_PASSWORD=${REDIS_PASSWORD}" > /usr/src/backend/app_recipe/.env

# העתקת כל קבצי האפליקציה
COPY app_recipe /usr/src/backend/app_recipe/

# חשיפת פורט FastAPI
EXPOSE 8093

# הפעלת האפליקציה
CMD ["python", "app_recipe/main.py"]
