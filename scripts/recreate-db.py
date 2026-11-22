import subprocess
import secrets
import sys
import time

project_id = "wcruz-ai-researcher-capstone"
instance_name = "ai-researcher-db"
db_name = "ai_researcher"
user_name = "app_user"
region = "us-central1"
connection_name = f"{project_id}:{region}:{instance_name}"

print("=== 1. Deleting existing Cloud SQL instance (if any) ===")
subprocess.run([
    "gcloud", "sql", "instances", "delete", instance_name,
    f"--project={project_id}",
    "--quiet"
], capture_output=True)
print("Deletion request sent (or instance did not exist).")

print("=== 2. Creating Cloud SQL instance ===")
res = subprocess.run([
    "gcloud", "sql", "instances", "create", instance_name,
    "--database-version=POSTGRES_16",
    "--tier=db-f1-micro",
    "--edition=ENTERPRISE",
    f"--region={region}",
    f"--project={project_id}"
])

if res.returncode != 0:
    print("Error creating instance.", file=sys.stderr)
    sys.exit(1)
print("Cloud SQL instance created successfully.")

print("=== 3. Creating database ===")
res = subprocess.run([
    "gcloud", "sql", "databases", "create", db_name,
    f"--instance={instance_name}",
    f"--project={project_id}"
], capture_output=True, text=True)

if res.returncode != 0:
    print(f"Error creating database: {res.stderr}", file=sys.stderr)
    sys.exit(1)
print("Database created successfully.")

print("=== 4. Generating password and creating user ===")
password = secrets.token_urlsafe(32)
res = subprocess.run([
    "gcloud", "sql", "users", "create", user_name,
    f"--instance={instance_name}",
    f"--password={password}",
    f"--project={project_id}"
], capture_output=True, text=True)

if res.returncode != 0:
    print(f"Error creating user: {res.stderr}", file=sys.stderr)
    sys.exit(1)
print("User app_user created successfully.")

print("=== 5. Setting temporary password for postgres user ===")
subprocess.run([
    "gcloud", "sql", "users", "set-password", "postgres",
    f"--instance={instance_name}",
    "--password=temp-password-123",
    f"--project={project_id}"
], capture_output=True, text=True)

print("=== 6. Starting cloud-sql-proxy ===")
proxy_path = "/home/wander/.local/bin/cloud-sql-proxy"
proxy_process = subprocess.Popen([
    proxy_path, connection_name, "--port=5432"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Wait a moment for proxy to start
time.sleep(3)

print("=== 7. Enabling vector extension via Node.js script ===")
# Run enable script
enable_res = subprocess.run([
    "node", "/home/wander/.gemini/tmp/capstone-project-ai-researcher/enable_vector.js"
], capture_output=True, text=True, cwd="/home/wander/.gemini/tmp/capstone-project-ai-researcher")

# Terminate proxy
proxy_process.terminate()
proxy_process.wait()

if enable_res.returncode != 0:
    print(f"Error enabling vector extension: {enable_res.stderr}", file=sys.stderr)
    sys.exit(1)
print("Vector extension enabled successfully.")

print("=== 8. Updating Secret Manager with new connection string ===")
conn_string = f"postgresql://{user_name}:{password}@/{db_name}?host=/cloudsql/{connection_name}"

# Add secret version
add_version = subprocess.run([
    "gcloud", "secrets", "versions", "add", "database-url",
    "--data-file=-",
    f"--project={project_id}"
], input=conn_string, capture_output=True, text=True)

if add_version.returncode != 0:
    print(f"Error adding secret version: {add_version.stderr}", file=sys.stderr)
    sys.exit(1)

print("SUCCESS: Cloud SQL recreated and Secret Manager updated with new credentials!")
