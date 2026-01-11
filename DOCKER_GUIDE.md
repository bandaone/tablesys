# 🐳 TABLESYS Docker Complete Guide

## Quick Start with Docker

The **easiest way** to run TABLESYS is using Docker. Everything is containerized and ready to go!

### Prerequisites
- Docker Desktop installed
- Docker Compose installed (included with Docker Desktop)

### One-Command Start

```bash
cd c:\SYSTEMS\TABLESYS
docker-compose up -d
```

That's it! The system will:
1. Start PostgreSQL database
2. Start FastAPI backend
3. Start React frontend
4. Seed the database with default users

### Access the System

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Database:** localhost:5432

## 🎯 Simple Username-Only Login

**No passwords required!** Just enter a username:

### Coordinators (Full Access)
- **coordinator** or **admin**

### HODs (Department-Specific Access)
- **MEC** - Mechanical Engineering HOD
- **CS** - Computer Science HOD
- **MATH** - Mathematics HOD
- **ELE** - Electrical Engineering HOD
- **CIV** - Civil Engineering HOD
- **PHY** - Physics HOD
- **CHEM** - Chemistry HOD
- **BIO** - Biology HOD

## Docker Commands

### Start Services
```bash
docker-compose up -d
```

### View Logs
```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend

# Database only
docker-compose logs -f postgres
```

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Rebuild Containers (after code changes)
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Check Running Containers
```bash
docker-compose ps
```

### Access Container Shell

```bash
# Backend container
docker-compose exec backend bash

# Frontend container
docker-compose exec frontend sh

# Database container
docker-compose exec postgres psql -U tablesys -d tablesys_db
```

## Container Details

### PostgreSQL Container
- **Image:** postgres:15-alpine
- **Port:** 5432
- **Database:** tablesys_db
- **User:** tablesys
- **Password:** tablesys123
- **Volume:** postgres_data (persistent storage)

### Backend Container
- **Build:** ./backend/Dockerfile
- **Port:** 8000
- **Framework:** FastAPI
- **Auto-reload:** Enabled
- **Dependencies:** Installed from requirements.txt

### Frontend Container
- **Build:** ./frontend/Dockerfile
- **Port:** 3000
- **Framework:** React + Vite
- **Hot-reload:** Enabled
- **Dependencies:** Installed from package.json

## Environment Variables

### Backend (.env in docker-compose.yml)
```yaml
DATABASE_URL: postgresql://tablesys:tablesys123@postgres:5432/tablesys_db
SECRET_KEY: your-secret-key-change-in-production
ALGORITHM: HS256
ACCESS_TOKEN_EXPIRE_MINUTES: 30
```

### Frontend
```yaml
VITE_API_URL: http://localhost:8000
```

## Volume Management

### List Volumes
```bash
docker volume ls
```

### Backup Database
```bash
docker-compose exec postgres pg_dump -U tablesys tablesys_db > backup.sql
```

### Restore Database
```bash
cat backup.sql | docker-compose exec -T postgres psql -U tablesys -d tablesys_db
```

### Clear All Data (Fresh Start)
```bash
docker-compose down -v  # Removes volumes
docker-compose up -d
```

## Network Configuration

All containers are on the same network: `tablesys-network`

### View Network
```bash
docker network inspect tablesys_tablesys-network
```

### Container Communication
- Backend connects to database using hostname: `postgres`
- Frontend connects to backend through host proxy

## Troubleshooting Docker

### Ports Already in Use

```bash
# Check what's using the port
netstat -ano | findstr :8000
netstat -ano | findstr :3000
netstat -ano | findstr :5432

# Stop the process or change ports in docker-compose.yml
```

### Container Won't Start

```bash
# Check logs
docker-compose logs backend
docker-compose logs frontend

# Rebuild without cache
docker-compose build --no-cache backend
docker-compose up -d
```

### Database Connection Issues

```bash
# Verify postgres is running
docker-compose ps

# Check database logs
docker-compose logs postgres

# Access database directly
docker-compose exec postgres psql -U tablesys -d tablesys_db
```

### Code Changes Not Reflecting

```bash
# For backend (auto-reloads)
docker-compose restart backend

# For frontend (should hot-reload)
docker-compose restart frontend

# If still not working, rebuild
docker-compose down
docker-compose build
docker-compose up -d
```

## Production Deployment

### Update docker-compose.yml for Production

```yaml
services:
  backend:
    environment:
      - DATABASE_URL=postgresql://user:pass@prod-db:5432/tablesys
      - SECRET_KEY=${SECRET_KEY}  # Use environment variable
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    
  frontend:
    build:
      context: ./frontend
      target: production
```

### Security Checklist

- [ ] Change default database password
- [ ] Set strong SECRET_KEY
- [ ] Use environment files (not hardcoded)
- [ ] Enable HTTPS
- [ ] Configure proper CORS
- [ ] Set up backup cron jobs
- [ ] Limit container resources
- [ ] Use Docker secrets for sensitive data

### Resource Limits

Add to docker-compose.yml:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## Development Workflow

### 1. Start Development Environment
```bash
docker-compose up -d
```

### 2. Make Code Changes
- Backend: Changes auto-reload
- Frontend: Changes hot-reload

### 3. View Changes
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs

### 4. Debug Issues
```bash
# View logs in real-time
docker-compose logs -f

# Access container
docker-compose exec backend bash
docker-compose exec frontend sh
```

### 5. Stop Development
```bash
docker-compose down
```

## Database Management

### Seed Database (Reset to Default Users)
```bash
docker-compose exec backend python seed_db.py
```

### Access PostgreSQL
```bash
docker-compose exec postgres psql -U tablesys -d tablesys_db
```

### Common SQL Commands
```sql
-- List all users
SELECT username, role, department_id FROM users;

-- List departments
SELECT * FROM departments;

-- Count courses
SELECT COUNT(*) FROM courses;

-- Reset database (WARNING: Deletes all data)
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO tablesys;
```

## Performance Optimization

### Cache Node Modules (Faster Builds)
```dockerfile
# In frontend/Dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

### Multi-Stage Python Build
```dockerfile
# In backend/Dockerfile
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

## Monitoring

### View Resource Usage
```bash
docker stats
```

### Health Checks
Add to docker-compose.yml:

```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Complete Docker Workflow Example

```bash
# 1. Clone or navigate to project
cd c:\SYSTEMS\TABLESYS

# 2. Start everything
docker-compose up -d

# 3. Wait for services to start (check logs)
docker-compose logs -f

# 4. Access frontend
# Open browser: http://localhost:3000

# 5. Login with username only
# Enter: coordinator (or MEC, CS, etc.)

# 6. Use the system
# Everything works automatically!

# 7. When done
docker-compose down

# 8. To start fresh (clear all data)
docker-compose down -v
docker-compose up -d
```

## Advantages of Docker Deployment

✅ **No Installation Hassles**
- No need to install Python, Node.js, or PostgreSQL
- Everything runs in containers

✅ **Consistent Environment**
- Works the same on Windows, Mac, Linux
- No "works on my machine" problems

✅ **Easy Updates**
- Pull new code, rebuild, restart
- No dependency conflicts

✅ **Simple Backup/Restore**
- Volume-based data persistence
- Easy database backups

✅ **Quick Setup**
- One command to start everything
- Automatic database seeding

## Summary

**To run TABLESYS with Docker:**

1. Install Docker Desktop
2. Run `docker-compose up -d`
3. Open http://localhost:3000
4. Login with username (no password!)
5. Start using the system!

**That's it!** Docker handles everything else automatically.

---

**For more help:** See main README.md or TROUBLESHOOTING.md
