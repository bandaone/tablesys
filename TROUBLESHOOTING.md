# 🔧 TABLESYS Troubleshooting Guide

Common issues and their solutions for TABLESYS.

## 🚨 Backend Issues

### Issue: Backend won't start

**Symptoms:**
- Error when running `uvicorn app.main:app --reload`
- Connection refused errors
- Import errors

**Solutions:**

1. **Check Python version**
   ```bash
   python --version
   # Should be 3.11 or higher
   ```

2. **Verify virtual environment is activated**
   ```bash
   cd backend
   venv\Scripts\activate
   # Prompt should show (venv)
   ```

3. **Reinstall dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Check for port conflicts**
   ```bash
   # Check if port 8000 is in use
   netstat -ano | findstr :8000
   # Kill the process if needed
   taskkill /PID <process_id> /F
   ```

### Issue: Database connection error

**Symptoms:**
- "could not connect to server"
- "database does not exist"
- "password authentication failed"

**Solutions:**

1. **Verify PostgreSQL is running**
   ```bash
   # Check PostgreSQL service
   sc query postgresql-x64-15
   # Start if not running
   net start postgresql-x64-15
   ```

2. **Check database exists**
   ```bash
   psql -U postgres -l
   # Look for tablesys_db
   ```

3. **Verify .env file**
   ```bash
   cd backend
   type .env
   # Check DATABASE_URL is correct
   ```

4. **Test connection manually**
   ```bash
   psql -U tablesys -d tablesys_db
   # Should connect without errors
   ```

5. **Recreate database if needed**
   ```sql
   DROP DATABASE IF EXISTS tablesys_db;
   CREATE DATABASE tablesys_db;
   GRANT ALL PRIVILEGES ON DATABASE tablesys_db TO tablesys;
   ```

### Issue: Import errors in Python

**Symptoms:**
- "ModuleNotFoundError"
- "No module named 'app'"

**Solutions:**

1. **Ensure you're in the correct directory**
   ```bash
   cd backend
   pwd  # Should show .../TABLESYS/backend
   ```

2. **Reinstall requirements**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Check app structure**
   ```bash
   dir app
   # Should show __init__.py and other files
   ```

### Issue: Database tables not created

**Symptoms:**
- "relation does not exist"
- "table not found"

**Solutions:**

1. **Run seed script**
   ```bash
   cd backend
   python seed_db.py
   ```

2. **Check database tables**
   ```sql
   psql -U tablesys -d tablesys_db
   \dt
   # Should show all tables
   ```

## 🌐 Frontend Issues

### Issue: Frontend won't start

**Symptoms:**
- Error when running `npm run dev`
- Port already in use
- Module not found errors

**Solutions:**

1. **Check Node version**
   ```bash
   node --version
   # Should be 18 or higher
   ```

2. **Delete and reinstall node_modules**
   ```bash
   cd frontend
   rd /s /q node_modules
   del package-lock.json
   npm install
   ```

3. **Clear npm cache**
   ```bash
   npm cache clean --force
   npm install
   ```

4. **Check for port conflicts**
   ```bash
   netstat -ano | findstr :3000
   # Kill process if needed
   taskkill /PID <process_id> /F
   ```

### Issue: "Cannot connect to backend"

**Symptoms:**
- Network errors in console
- API calls fail
- 404 errors

**Solutions:**

1. **Verify backend is running**
   ```bash
   # Open http://localhost:8000/docs
   # Should show Swagger UI
   ```

2. **Check proxy configuration**
   ```typescript
   // vite.config.ts
   proxy: {
     '/api': {
       target: 'http://localhost:8000',
       changeOrigin: true,
     }
   }
   ```

3. **Check CORS settings**
   ```python
   # backend/app/main.py
   allow_origins=["http://localhost:3000", "http://localhost:5173"]
   ```

### Issue: White screen / Nothing displays

**Symptoms:**
- Blank white page
- Console shows errors

**Solutions:**

1. **Check browser console (F12)**
   ```
   Look for red error messages
   ```

2. **Clear browser cache**
   ```
   Ctrl+Shift+Delete → Clear cache
   ```

3. **Try different browser**
   ```
   Test in Chrome, Firefox, Edge
   ```

4. **Rebuild frontend**
   ```bash
   cd frontend
   npm run build
   npm run preview
   ```

## 🔐 Authentication Issues

### Issue: Cannot login

**Symptoms:**
- "Invalid credentials" error
- Login button doesn't work
- Redirects back to login

**Solutions:**

1. **Verify default credentials**
   ```
   Username: admin
   Password: admin123
   ```

2. **Check database has admin user**
   ```sql
   psql -U tablesys -d tablesys_db
   SELECT * FROM users WHERE username='admin';
   ```

3. **Re-run seed script**
   ```bash
   cd backend
   python seed_db.py
   ```

4. **Check network tab in browser**
   ```
   F12 → Network → Try login → Check response
   ```

### Issue: "Token expired" errors

**Symptoms:**
- Logged out unexpectedly
- Actions fail with 401 error

**Solutions:**

1. **Clear localStorage**
   ```javascript
   // Browser console (F12)
   localStorage.clear();
   location.reload();
   ```

2. **Login again**
   ```
   Token expires after 30 minutes by default
   ```

3. **Check token expiry settings**
   ```python
   # backend/.env
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   ```

## 📤 Bulk Upload Issues

### Issue: Upload fails

**Symptoms:**
- "Error uploading file"
- "Invalid file format"
- Rows skipped

**Solutions:**

1. **Check file format**
   ```
   Must be .csv, .xlsx, or .xls
   ```

2. **Verify column names**
   ```csv
   # Courses example
   code,name,department_id,level,credits,lecture_hours,tutorial_hours,practical_hours
   ```

3. **Check data types**
   ```
   - IDs must be numbers
   - Booleans must be true/false
   - No empty required fields
   ```

4. **Download fresh template**
   ```
   Use the "Download Template" button
   ```

5. **Check for special characters**
   ```
   Remove commas, quotes, newlines in text fields
   ```

### Issue: Department ID errors

**Symptoms:**
- "department_id does not exist"
- Rows skipped due to department

**Solutions:**

1. **List existing departments**
   ```sql
   SELECT id, name, code FROM departments;
   ```

2. **Create missing departments first**
   ```
   Go to Departments page → Add manually
   ```

3. **Update CSV with correct IDs**
   ```csv
   CS101,Programming,1,2,3,3,1,2
   # Use actual department_id from database
   ```

## 🎯 Timetable Generation Issues

### Issue: Generation fails

**Symptoms:**
- "Failed to generate timetable"
- Stuck at certain percentage
- No solution found

**Solutions:**

1. **Check required data exists**
   ```
   - Courses must have assigned lecturers
   - Courses must have assigned groups
   - Rooms must be available
   ```

2. **Verify assignments**
   ```sql
   -- Check lecturer assignments
   SELECT * FROM lecturer_assignments;
   
   -- Check group assignments
   SELECT * FROM group_assignments;
   ```

3. **Ensure sufficient resources**
   ```
   - Enough rooms for all classes
   - Lecturers not overbooked
   - Time slots available
   ```

4. **Reduce constraints**
   ```
   - Temporarily remove some courses
   - Add more rooms
   - Increase time slots
   ```

### Issue: Generation takes too long

**Symptoms:**
- Stuck at "solving"
- Timeout errors
- Process hangs

**Solutions:**

1. **Increase timeout**
   ```python
   # backend/app/services/timetable_generator.py
   solver.parameters.max_time_in_seconds = 600  # 10 minutes
   ```

2. **Reduce problem size**
   ```
   - Generate fewer levels at once
   - Reduce number of courses
   - Simplify constraints
   ```

3. **Check system resources**
   ```bash
   # Task Manager → Performance
   # Ensure CPU and RAM available
   ```

### Issue: No progress updates

**Symptoms:**
- Progress bar stuck at 0%
- No status messages
- WebSocket not connecting

**Solutions:**

1. **Check WebSocket URL**
   ```
   Should be ws://localhost:8000/api/timetables/generate/{id}
   ```

2. **Verify backend running**
   ```bash
   # Backend terminal should show WebSocket connection
   ```

3. **Check browser console**
   ```
   F12 → Console → Look for WebSocket errors
   ```

4. **Try different browser**
   ```
   WebSocket support varies by browser
   ```

## 🐳 Docker Issues

### Issue: Docker containers won't start

**Symptoms:**
- "docker-compose up" fails
- Containers exit immediately
- Port binding errors

**Solutions:**

1. **Check Docker is running**
   ```bash
   docker --version
   docker ps
   ```

2. **Check port availability**
   ```bash
   netstat -ano | findstr :5432
   netstat -ano | findstr :8000
   netstat -ano | findstr :3000
   ```

3. **Rebuild containers**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

4. **Check logs**
   ```bash
   docker-compose logs backend
   docker-compose logs frontend
   docker-compose logs postgres
   ```

### Issue: Database connection in Docker

**Symptoms:**
- Backend can't connect to postgres
- "Connection refused" errors

**Solutions:**

1. **Verify network**
   ```bash
   docker network ls
   docker network inspect tablesys_tablesys-network
   ```

2. **Check DATABASE_URL**
   ```yaml
   # docker-compose.yml
   DATABASE_URL: postgresql://tablesys:tablesys123@postgres:5432/tablesys_db
   # Note: Use service name 'postgres', not 'localhost'
   ```

3. **Wait for postgres to be ready**
   ```yaml
   # Add health check to postgres service
   depends_on:
     postgres:
       condition: service_healthy
   ```

## 🔍 General Debugging

### Enable Debug Logging

**Backend:**
```python
# app/main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Frontend:**
```typescript
// Add console.log statements
console.log('API Response:', response);
```

### Check System Status

```bash
# Backend health
curl http://localhost:8000/health

# Frontend running
curl http://localhost:3000

# Database connection
psql -U tablesys -d tablesys_db -c "SELECT 1"
```

### Review Logs

```bash
# Backend logs (in terminal running uvicorn)
# Frontend logs (in terminal running npm)
# Browser console (F12)
# PostgreSQL logs (check PostgreSQL log directory)
```

## 📞 Getting Help

If issues persist:

1. **Check documentation**
   - README.md
   - SETUP_GUIDE.md
   - QUICK_REFERENCE.md

2. **Search error messages**
   - Copy exact error message
   - Search in documentation
   - Check Stack Overflow

3. **Collect information**
   - Error messages
   - System information
   - Steps to reproduce
   - Logs and screenshots

4. **Contact support**
   - Provide all collected information
   - Describe what you've already tried

## ✅ Prevention Tips

1. **Regular backups**
   ```bash
   pg_dump -U tablesys tablesys_db > backup.sql
   ```

2. **Keep dependencies updated**
   ```bash
   pip list --outdated
   npm outdated
   ```

3. **Monitor logs regularly**
   ```bash
   # Check for warnings and errors
   ```

4. **Test in development first**
   ```bash
   # Never test directly in production
   ```

5. **Document changes**
   ```bash
   # Keep track of customizations
   ```

## 🎯 Quick Fixes

### Reset Everything
```bash
# Nuclear option - fresh start
cd c:\SYSTEMS\TABLESYS

# Drop database
psql -U postgres -c "DROP DATABASE tablesys_db;"
psql -U postgres -c "CREATE DATABASE tablesys_db;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE tablesys_db TO tablesys;"

# Clean backend
cd backend
rd /s /q venv
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python seed_db.py

# Clean frontend
cd ..\frontend
rd /s /q node_modules
npm install

# Start fresh
cd ..
start.bat
```

---

**Remember:** Most issues can be resolved by checking logs and error messages carefully!

If you're stuck, refer to SETUP_GUIDE.md or contact support.
