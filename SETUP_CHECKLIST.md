# 📋 TABLESYS First-Time Setup Checklist

Use this checklist to ensure proper system setup and configuration.

## ✅ Pre-Installation

- [ ] Windows 10/11 installed
- [ ] Python 3.11+ installed and in PATH
  - [ ] Verify: `python --version`
- [ ] Node.js 18+ installed
  - [ ] Verify: `node --version`
  - [ ] Verify: `npm --version`
- [ ] PostgreSQL 15+ installed and running
  - [ ] Verify: `psql --version`
  - [ ] PostgreSQL service is running
- [ ] Git installed (optional, for version control)

## ✅ Database Setup

- [ ] PostgreSQL service is running
- [ ] Create database: `tablesys_db`
  ```sql
  CREATE DATABASE tablesys_db;
  ```
- [ ] Create database user: `tablesys`
  ```sql
  CREATE USER tablesys WITH PASSWORD 'tablesys123';
  ```
- [ ] Grant privileges
  ```sql
  GRANT ALL PRIVILEGES ON DATABASE tablesys_db TO tablesys;
  ```
- [ ] Test connection
  ```bash
  psql -U tablesys -d tablesys_db
  ```

## ✅ Project Setup

- [ ] Navigate to project directory
  ```bash
  cd c:\SYSTEMS\TABLESYS
  ```
- [ ] Run setup script
  ```bash
  setup.bat
  ```
- [ ] Wait for setup to complete
- [ ] Check for any error messages

## ✅ Backend Configuration

- [ ] Navigate to backend directory
  ```bash
  cd backend
  ```
- [ ] Verify .env file exists
- [ ] Open .env file and verify settings:
  ```
  DATABASE_URL=postgresql://tablesys:tablesys123@localhost:5432/tablesys_db
  SECRET_KEY=your-secret-key-here-change-in-production
  ALGORITHM=HS256
  ACCESS_TOKEN_EXPIRE_MINUTES=30
  ```
- [ ] Update SECRET_KEY with a secure value (for production)
- [ ] Verify virtual environment was created: `venv/` folder exists
- [ ] Verify database tables were created (check PostgreSQL)

## ✅ Frontend Configuration

- [ ] Navigate to frontend directory
  ```bash
  cd frontend
  ```
- [ ] Verify node_modules exists
- [ ] Check package.json for correct dependencies

## ✅ First Run

- [ ] Start the system
  ```bash
  cd c:\SYSTEMS\TABLESYS
  start.bat
  ```
- [ ] Wait for both servers to start
- [ ] Backend should be running on port 8000
- [ ] Frontend should be running on port 3000

## ✅ Access Verification

- [ ] Open browser
- [ ] Navigate to http://localhost:3000
- [ ] Login page loads successfully
- [ ] University of Zambia colors are visible (Dark Blue, Orange)
- [ ] Login with default credentials:
  - Username: `admin`
  - Password: `admin123`
- [ ] Dashboard loads successfully
- [ ] Navigation menu is visible
- [ ] User name appears in top right

## ✅ API Verification

- [ ] Open http://localhost:8000/docs in browser
- [ ] Swagger UI documentation loads
- [ ] All endpoints are listed
- [ ] Can expand and view endpoint details

## ✅ Functionality Testing

### Test Authentication
- [ ] Can login successfully
- [ ] Can logout
- [ ] Invalid credentials are rejected

### Test Navigation
- [ ] Dashboard page loads
- [ ] Courses page loads
- [ ] Lecturers page loads
- [ ] Rooms page loads
- [ ] Groups page loads
- [ ] Timetables page loads
- [ ] Departments page loads

### Test Data Entry
- [ ] Can create a department (Coordinator only)
  - [ ] Name: "Computer Science"
  - [ ] Code: "CS"
- [ ] Department appears in list

## ✅ Bulk Upload Testing

### Test Course Upload
- [ ] Navigate to Courses page
- [ ] Click "Bulk Upload"
- [ ] Dialog opens
- [ ] Click "Download Template"
- [ ] Template downloads successfully
- [ ] Open template in Excel
- [ ] Add sample data:
  ```
  CS101,Introduction to Programming,1,2,3,3,1,2
  ```
- [ ] Save as CSV or Excel
- [ ] Upload file
- [ ] Success message appears
- [ ] Course appears in courses list

### Test Lecturer Upload
- [ ] Navigate to Lecturers page
- [ ] Follow same process as courses
- [ ] Sample data:
  ```
  L001,Dr. John Doe,j.doe@unza.zm,1,20
  ```
- [ ] Verify lecturer appears

### Test Room Upload
- [ ] Navigate to Rooms page
- [ ] Sample data:
  ```
  R101,Main Building,50,lecture,true,false
  ```
- [ ] Verify room appears

### Test Group Upload
- [ ] Navigate to Groups page
- [ ] Sample data:
  ```
  CS-5A,5,1,45
  ```
- [ ] Verify group appears

## ✅ Timetable Generation Testing

- [ ] Navigate to Timetables page
- [ ] Click "Create Timetable"
- [ ] Fill in details:
  - Name: "Test Timetable"
  - Semester: "Semester 1"
  - Year: 2026
- [ ] Timetable created successfully
- [ ] Click "Generate Timetable"
- [ ] Generation dialog opens
- [ ] Click "Start Generation"
- [ ] Progress bar appears
- [ ] Progress updates in real-time:
  - [ ] "Creating 5th year timetable..." appears
  - [ ] Progress reaches 25%
  - [ ] "Creating 4th year timetable..." appears
  - [ ] Progress reaches 50%
  - [ ] "Creating 3rd year timetable..." appears
  - [ ] Progress reaches 75%
  - [ ] "Creating 2nd year timetable..." appears
  - [ ] Progress reaches 100%
  - [ ] Success message appears

## ✅ Role-Based Access Testing

### Create HOD User (as Coordinator)
- [ ] Create new department "Mathematics" if not exists
- [ ] Create new user:
  - Username: `hod_math`
  - Password: `test123`
  - Role: HOD
  - Department: Mathematics
- [ ] Logout
- [ ] Login as HOD user

### Test HOD Restrictions
- [ ] Can view courses in Mathematics department
- [ ] Cannot view courses in other departments
- [ ] Can view lecturers in Mathematics
- [ ] Cannot access Rooms page (menu item hidden)
- [ ] Cannot access Groups page (menu item hidden)
- [ ] Cannot access Departments page (menu item hidden)
- [ ] Can upload courses for Mathematics only
- [ ] Cannot upload for other departments
- [ ] Can view timetables
- [ ] Cannot generate timetables

## ✅ Performance Verification

- [ ] Pages load within 2 seconds
- [ ] Bulk upload processes within reasonable time
- [ ] Timetable generation completes (may take several minutes)
- [ ] No console errors in browser (F12 → Console)
- [ ] No errors in backend terminal
- [ ] No errors in frontend terminal

## ✅ Security Verification

- [ ] Cannot access dashboard without login
- [ ] Redirected to login when not authenticated
- [ ] HOD cannot access coordinator-only features
- [ ] Logout works properly
- [ ] Session persists on page refresh (while valid)

## ✅ Documentation Review

- [ ] README.md reviewed
- [ ] SETUP_GUIDE.md reviewed
- [ ] QUICK_REFERENCE.md reviewed
- [ ] SYSTEM_SUMMARY.md reviewed

## ✅ Production Preparation

### Security
- [ ] Change default admin password
- [ ] Update SECRET_KEY in .env
- [ ] Review CORS settings in main.py
- [ ] Set strong database password
- [ ] Disable debug mode if enabled

### Backup
- [ ] Set up database backup schedule
- [ ] Test database backup/restore
- [ ] Document backup procedures

### Monitoring
- [ ] Set up log monitoring
- [ ] Configure error alerts
- [ ] Document troubleshooting procedures

## ✅ Final Checklist

- [ ] All tests passed
- [ ] System is stable
- [ ] Documentation is complete
- [ ] Users are trained
- [ ] Backup system is in place
- [ ] Support contacts are documented
- [ ] Go-live date is scheduled

## 🎯 Post-Setup Tasks

1. **Change Default Password**
   - Login as admin
   - Navigate to profile
   - Change password to something secure

2. **Create Department Structure**
   - Add all university departments
   - Create HOD users for each department
   - Assign HODs to their departments

3. **Import Initial Data**
   - Bulk upload all courses
   - Bulk upload all lecturers
   - Bulk upload all rooms
   - Bulk upload student groups

4. **Configure Assignments**
   - Assign lecturers to courses
   - Assign student groups to courses

5. **Generate First Timetable**
   - Create timetable for current semester
   - Generate and review
   - Make adjustments as needed
   - Activate when satisfied

6. **Train Users**
   - Train HODs on their access level
   - Demonstrate bulk upload process
   - Show how to view timetables
   - Answer questions

## 📞 Support Contacts

If you encounter issues during setup:

1. Check SETUP_GUIDE.md for detailed instructions
2. Review error messages carefully
3. Check backend and frontend logs
4. Verify database connection
5. Contact development team

## ✅ Setup Complete!

When all items are checked:
- [ ] System is fully operational
- [ ] All tests passed
- [ ] Ready for production use

---

**Congratulations!** 🎉 TABLESYS is now set up and ready to use!

Remember to:
- Keep regular backups
- Monitor system performance
- Update documentation as needed
- Train new users properly
- Maintain security best practices

**Built for the University of Zambia** 🇿🇲
