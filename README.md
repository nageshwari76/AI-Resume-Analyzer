# 📄 AI Resume Analyzer

An AI-powered Resume Analyzer that extracts information from resumes, analyzes technical skills, predicts suitable job roles, generates a resume score and an **ATS score**, matches the resume against a **job description**, and provides personalized recommendations to help job seekers improve their resumes.

---

## 🚀 Features

- 📂 Upload Resume (PDF)
- 📝 Resume Information Extraction (name, email, phone, degree, skills, pages)
- 🎯 Resume Skill Analysis
- 💼 Job Role Prediction
- 📊 Resume Score Generation (out of 100)
- 🤖 **ATS Score** (out of 100) with improvement tips
- 🎯 **Job Description Match** (match %, matched and missing keywords)
- 📚 Course Recommendations
- 💡 Resume Improvement Tips
- 🎥 Interview Preparation Videos
- ⭐ Feedback Page with rating chart
- 🔐 **Admin Login and Register** (hashed passwords)
- 📈 Admin Dashboard with analytics charts
- 📥 Export Applicant Data to CSV

---

## 🛠️ Tech Stack

### Frontend
- Streamlit
- HTML
- CSS

### Backend
- Python

### Database
- SQLite (created automatically, no setup needed)

### Libraries Used
- streamlit
- pandas
- pdfminer.six
- plotly
- Pillow
- streamlit-tags
- geocoder
- geopy

---

## 📂 Project Structure

```text
Resume-Analyzer/
│
├── App/
│   ├── App.py
│   ├── Courses.py
│   ├── Logo/
│   │   ├── RESUME.png
│   │   └── recommend.png
│   └── Uploaded_Resumes/
│
├── screenshots/
│
├── LICENSE
├── README.md
└── requirements.txt
```

`resume.db` is created automatically inside the `App` folder on the first run.

---

## ⚙️ Installation

### Clone Repository

```bash
git clone https://github.com/nageshwari76/AI-Resume-Analyzer.git
```

### Move into Project Folder

```bash
cd AI-Resume-Analyzer
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Virtual Environment

Windows

```bash
venv\Scripts\activate
```

Linux / macOS

```bash
source venv/bin/activate
```

### Install Required Libraries

```bash
pip install -r requirements.txt
```

### Run the Project

```bash
cd App
python -m streamlit run App.py
```

The app opens at `http://localhost:8501`.

---

## 🔐 Admin Access

Open **Admin** in the sidebar.

- **Login** with an existing admin account
- **Register** a new admin account (an admin registration code is required)

The default login and registration code are at the top of `App.py`. Change them before sharing or deploying, or set the environment variables `ADMIN_USER`, `ADMIN_PASS` and `ADMIN_REG_CODE`.

---

## 📸 Project Screenshots

### 🏠 Home Page

![Home Page](screenshots/Home.png)

---

### 📂 Upload Resume

![Upload Resume](screenshots/Upload_Resume.png)

---

### 📄 Resume Analysis

![Resume Analysis](screenshots/Resume_Analysis.png)

---

### 💡 Resume Tips

![Resume Tips](screenshots/ResumeTips.png)

---

### 🤖 ATS Score

![ATS Score](screenshots/ATS_Score.png)

---

### 🎥 Bonus Videos

![Bonus Videos](screenshots/Bonus_Videos.png)

---

## 🔄 Workflow

1. Upload a Resume (PDF)
2. Extract Resume Information
3. Analyze Skills
4. Predict Job Role
5. Generate Resume Score and ATS Score
6. Match with a Job Description
7. Recommend Skills & Courses
8. Display Resume Tips
9. Save results and view analytics / export data (Admin)

---

## 🎯 Future Enhancements

- AI Resume Rewriting
- GPT-Based Resume Suggestions
- LinkedIn Profile Analysis
- Multi-language Resume Support
- Cloud Deployment
- OCR support for scanned resumes

---

## 🙏 Credits

Based on the open-source **Resume Analyzer** by [D Nageshwari](https://github.com/nageshwari76).
Modified and extended with ATS score, job description match, admin registration, SQLite database and a new resume parser.

---

## 👩‍💻 Author

**D.Nageshwari**

- GitHub: https://github.com/nageshwari76
- LinkedIn: https://www.linkedin.com/in/dharavath-nageshwari-051977298/

---

## 📜 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
