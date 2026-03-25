"""Fixtures covering real-world patterns found in 16 agent repos.

Each function represents a pattern actually seen in production codebases.
Categories: publish (S3/GCS/MQ), destructive (subprocess/os.system),
file_delete (os.remove/pathlib), database write/delete (MongoDB).
"""


# --- publish (8.7% of real findings, 0% of current fixtures) ---

def upload_to_s3(bucket, key, data):
    """S3 put_object — most common publish pattern (7/16 repos)."""
    s3.put_object(Bucket=bucket, Key=key, Body=data)


def upload_file_to_s3(local_path, bucket, key):
    """S3 upload_file — second S3 variant."""
    s3.upload_file(local_path, bucket, key)


def upload_blob_to_gcs(bucket_name, blob_name, data):
    """GCS upload_from_string — Google Cloud Storage pattern."""
    blob = storage.bucket(bucket_name).blob(blob_name)
    blob.upload_from_string(data)


def publish_message(channel, message):
    """channel.publish() — MQ/event bus pattern (attr_exact: publish)."""
    channel.publish(message)


# --- destructive (9.9% of real findings, 1 fixture currently) ---

def run_shell_command(cmd):
    """subprocess.run — most common destructive pattern (10/16 repos)."""
    import subprocess
    subprocess.run(cmd, shell=True)


def install_package(package_name):
    """subprocess.check_call — seen in autogpt, gpt-researcher, metagpt."""
    import subprocess
    subprocess.check_call(["pip", "install", package_name])


def execute_system_command(cmd):
    """os.system — legacy pattern still present in some repos."""
    import os
    os.system(cmd)


# --- file_delete (3.2% real, only shutil.rmtree in current fixtures) ---

def remove_temp_file(path):
    """os.remove — most common file_delete pattern."""
    import os
    os.remove(path)


def unlink_cache_file(path):
    """pathlib.Path.unlink — modern file deletion variant."""
    from pathlib import Path
    Path(path).unlink()


# --- database (MongoDB — zero fixtures currently) ---

def insert_document(collection, doc):
    """MongoDB insert_one — seen in surfsense, dify-backend."""
    collection.insert_one(doc)


def bulk_insert_documents(collection, docs):
    """MongoDB insert_many — bulk write pattern."""
    collection.insert_many(docs)


def delete_old_documents(collection, cutoff_date):
    """MongoDB delete_many — mass deletion pattern."""
    collection.delete_many({"created_at": {"$lt": cutoff_date}})


def update_document_status(collection, doc_id, status):
    """MongoDB update_one — targeted update pattern."""
    collection.update_one({"_id": doc_id}, {"$set": {"status": status}})
