# 📤 Push TABLESYS to GitHub

## Step 1: Install Git

If you don't have Git installed:

1. Download Git for Windows from: https://git-scm.com/download/win
2. Run the installer (use default settings)
3. Restart VS Code/PowerShell after installation

## Step 2: Create GitHub Repository

1. Go to https://github.com
2. Click the **+** icon (top right) → **New repository**
3. Repository details:
   - **Name:** `TABLESYS` or `unza-timetable-system`
   - **Description:** `University Timetable Management System for UNZA`
   - **Visibility:** Choose Public or Private
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
4. Click **Create repository**
5. Copy the repository URL (e.g., `https://github.com/yourusername/TABLESYS.git`)

## Step 3: Initialize Git and Push

Open PowerShell in the project directory and run:

```powershell
cd c:\SYSTEMS\TABLESYS

# Initialize git repository
git init

# Configure git (first time only)
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Add all files
git add .

# Create first commit
git commit -m "Initial commit: Complete TABLESYS with Docker and username-only auth"

# Add your GitHub repository as remote
git remote add origin https://github.com/yourusername/TABLESYS.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**Replace `https://github.com/yourusername/TABLESYS.git` with your actual GitHub repository URL!**

## Step 4: Verify

1. Refresh your GitHub repository page
2. You should see all files uploaded
3. The README.md will be displayed on the repository homepage

## Alternative: Using GitHub Desktop

If you prefer a GUI:

1. Download GitHub Desktop: https://desktop.github.com/
2. Install and sign in to GitHub
3. Click **File** → **Add Local Repository**
4. Select `c:\SYSTEMS\TABLESYS`
5. Click **Publish repository**
6. Choose name, description, and visibility
7. Click **Publish repository**

## Common Issues

### "Git is not recognized"
- Git is not installed or not in PATH
- Solution: Install Git from https://git-scm.com/download/win and restart terminal

### "Permission denied (publickey)"
- Using SSH URL without SSH keys configured
- Solution: Use HTTPS URL instead or set up SSH keys

### "Failed to push some refs"
- Remote repository has files you don't have locally
- Solution: Run `git pull origin main --allow-unrelated-histories` first, then push

### Large files rejected
- GitHub has 100MB file size limit
- Solution: Already handled by .gitignore (excludes node_modules, venv, etc.)

## What Gets Pushed

✅ **Included:**
- All source code (backend & frontend)
- Docker configuration
- Documentation (README, guides)
- Requirements and package files
- Configuration files

❌ **Excluded (via .gitignore):**
- node_modules/
- venv/
- __pycache__/
- postgres_data/
- .env files
- Build artifacts
- IDE settings

## Repository Structure on GitHub

```
TABLESYS/
├── backend/
│   ├── app/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── seed_db.py
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── Dockerfile
│   └── vite.config.ts
├── docker-compose.yml
├── README.md
├── DOCKER_GUIDE.md
├── SETUP_GUIDE.md
├── QUICK_REFERENCE.md
├── SYSTEM_SUMMARY.md
├── SETUP_CHECKLIST.md
├── TROUBLESHOOTING.md
├── setup.bat
├── start.bat
└── .gitignore
```

## Post-Push Actions

### Add Repository Topics (Optional)
On GitHub repository page, click **⚙️ Settings** → **Add topics**:
- `timetable-system`
- `fastapi`
- `react`
- `typescript`
- `docker`
- `postgresql`
- `university`
- `scheduling`

### Enable GitHub Actions (Optional)
Create `.github/workflows/docker-build.yml` for automated builds

### Add Repository Description
Edit the "About" section on GitHub with:
```
🎓 University Timetable Management System for UNZA with automated scheduling, Docker deployment, and role-based access control
```

### Add Website Link
If deployed online, add the URL to repository settings

## Cloning the Repository Later

To clone on another machine:

```bash
git clone https://github.com/yourusername/TABLESYS.git
cd TABLESYS
docker-compose up -d
```

## Making Updates

After making changes to code:

```bash
# Check what changed
git status

# Add changes
git add .

# Commit with descriptive message
git commit -m "Add feature X" 

# Push to GitHub
git push
```

## Branching Strategy (Optional)

For team development:

```bash
# Create development branch
git checkout -b development

# Create feature branch
git checkout -b feature/new-algorithm

# Merge back to main
git checkout main
git merge feature/new-algorithm
git push
```

## Complete Push Command Summary

```powershell
# One-time setup
cd c:\SYSTEMS\TABLESYS
git init
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
git add .
git commit -m "Initial commit: Complete TABLESYS with Docker and username-only auth"
git remote add origin https://github.com/yourusername/TABLESYS.git
git branch -M main
git push -u origin main

# Future updates
git add .
git commit -m "Your commit message"
git push
```

## Need Help?

- GitHub Docs: https://docs.github.com
- Git Documentation: https://git-scm.com/doc
- GitHub Desktop: https://desktop.github.com

---

**Ready to push!** Follow Step 1-3 above and your project will be on GitHub.
