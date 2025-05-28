import os
import boto3
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Read credentials from env
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")

# Initialize the R2 S3 client
s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY
)

def upload_file(local_path: str, object_name: str = None):
    if not object_name:
        object_name = os.path.basename(local_path)

    try:
        s3.upload_file(local_path, R2_BUCKET_NAME, object_name)
        print(f"✅ Uploaded: {object_name}")
    except Exception as e:
        print("❌ Upload failed:", e)
        return None
    return object_name

def generate_presigned_url(object_name: str, expiration=3600):
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': R2_BUCKET_NAME, 'Key': object_name},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        print("❌ Failed to generate URL:", e)
        return None

# Example usage
if __name__ == "__main__":
    file_path = "CloudIcon.png"  # change to your file
    key_name = upload_file(file_path)
    if key_name:
        url = generate_presigned_url(key_name)
        print("📦 File URL:", url)
