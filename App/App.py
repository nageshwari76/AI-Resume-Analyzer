###### Packages Used ######
import base64
import datetime
import getpass
import hashlib
import hmac
import os
import platform
import random
import re
import secrets
import socket
import sqlite3
import time

import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import Image
from streamlit_tags import st_tags
from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

# Optional packages (app still runs if they are missing / offline)
try:
    import geocoder
except Exception:
    geocoder = None
try:
    from geopy.geocoders import Nominatim
except Exception:
    Nominatim = None

# pre stored data for recommendations (your own Courses.py is used if present)
try:
    from Courses import (ds_course, web_course, android_course, ios_course,
                         uiux_course, resume_videos, interview_videos)
except Exception:
    _c = "https://www.coursera.org/search?query="
    ds_course = [("Machine Learning", _c + "machine+learning")]
    web_course = [("Web Development", _c + "web+development")]
    android_course = [("Android Development", _c + "android+development")]
    ios_course = [("iOS Development", _c + "ios+development")]
    uiux_course = [("UI/UX Design", _c + "ux+design")]
    resume_videos = []
    interview_videos = []

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "Uploaded_Resumes")
DB_PATH = os.path.join(BASE_DIR, "resume.db")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin@resume-analyzer")
# code required to create a new admin account (change it, or set the ADMIN_REG_CODE env variable)
ADMIN_REG_CODE = os.environ.get("ADMIN_REG_CODE", "resume-admin-2026")

st.set_page_config(page_title="AI Resume Analyzer", page_icon="📄")


###### Database (SQLite) ######

@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS user_data (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        sec_token TEXT, ip_add TEXT, host_name TEXT, dev_user TEXT,
        os_name_ver TEXT, latlong TEXT, city TEXT, state TEXT, country TEXT,
        act_name TEXT, act_mail TEXT, act_mob TEXT,
        Name TEXT, Email_ID TEXT, resume_score TEXT, Timestamp TEXT,
        Page_no TEXT, Predicted_Field TEXT, User_level TEXT,
        Actual_skills TEXT, Recommended_skills TEXT,
        Recommended_courses TEXT, pdf_name TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS user_feedback (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        feed_name TEXT, feed_email TEXT, feed_score TEXT,
        comments TEXT, Timestamp TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS admin_users (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL, full_name TEXT, email TEXT,
        salt TEXT NOT NULL, pw_hash TEXT NOT NULL, created TEXT)""")
    # add new columns to databases created by the earlier version
    existing = {row[1] for row in conn.execute("PRAGMA table_info(user_data)")}
    for col in ("ats_score", "jd_match"):
        if col not in existing:
            conn.execute(f"ALTER TABLE user_data ADD COLUMN {col} TEXT")
    conn.commit()
    return conn


conn = get_conn()


def insert_data(*values):
    cur = conn.execute("""INSERT INTO user_data (sec_token, ip_add, host_name, dev_user,
        os_name_ver, latlong, city, state, country, act_name, act_mail, act_mob,
        Name, Email_ID, resume_score, Timestamp, Page_no, Predicted_Field,
        User_level, Actual_skills, Recommended_skills, Recommended_courses,
        pdf_name, ats_score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 [str(v) for v in values])
    conn.commit()
    return cur.lastrowid


def update_jd_match(row_id, pct):
    conn.execute("UPDATE user_data SET jd_match = ? WHERE ID = ?", (str(pct), row_id))
    conn.commit()


def insertf_data(name, email, score, comments, ts):
    conn.execute("""INSERT INTO user_feedback (feed_name, feed_email, feed_score,
        comments, Timestamp) VALUES (?,?,?,?,?)""",
                 (name, email, str(score), comments, ts))
    conn.commit()


###### Admin accounts ######

def _hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()


def register_admin(username, full_name, email, password):
    """Returns (ok, message)."""
    username = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", username):
        return False, "Username must be 3-30 characters (letters, numbers, _ . -)."
    if username.lower() == ADMIN_USER.lower():
        return False, "That username is reserved."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
        return False, "Please enter a valid email address."
    salt = secrets.token_hex(16)
    try:
        conn.execute("INSERT INTO admin_users (username, full_name, email, salt, pw_hash, created)"
                     " VALUES (?,?,?,?,?,?)",
                     (username, full_name.strip(), email.strip(), salt,
                      _hash_pw(password, salt), now_stamp()))
        conn.commit()
    except sqlite3.IntegrityError:
        return False, "This username is already taken."
    return True, "Registration successful! You can now log in."


def check_admin_login(username, password):
    """Returns the display name on success, otherwise None."""
    username = username.strip()
    if username == ADMIN_USER and hmac.compare_digest(password, ADMIN_PASS):
        return username
    row = conn.execute("SELECT salt, pw_hash, full_name FROM admin_users WHERE username = ?",
                       (username,)).fetchone()
    if row and hmac.compare_digest(_hash_pw(password, row[0]), row[1]):
        return row[2] or username
    return None


###### Helper functions ######

def now_stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")


def get_csv_download_link(df, filename, text):
    b64 = base64.b64encode(df.to_csv(index=False).encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'


def show_pdf(file_path):
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}" width="700" '
        f'height="1000" type="application/pdf"></iframe>',
        unsafe_allow_html=True)


def count_pages(path):
    with open(path, "rb") as f:
        return sum(1 for _ in PDFPage.get_pages(f))


def has_any(text, words):
    t = text.lower()
    return any(w.lower() in t for w in words)


KNOWN_SKILLS = [
    "python", "java", "c", "c++", "c#", "javascript", "typescript", "sql", "mysql",
    "mongodb", "html", "css", "react", "react js", "angular js", "node js", "django",
    "flask", "streamlit", "php", "laravel", "magento", "wordpress", "asp.net",
    "tensorflow", "keras", "pytorch", "machine learning", "deep learning",
    "data analysis", "data science", "pandas", "numpy", "scikit-learn", "nlp",
    "android", "android development", "flutter", "kotlin", "xml", "kivy",
    "ios", "ios development", "swift", "cocoa", "cocoa touch", "xcode",
    "ux", "ui", "adobe xd", "figma", "zeplin", "balsamiq", "prototyping",
    "wireframes", "wireframe", "adobe photoshop", "photoshop", "editing",
    "adobe illustrator", "illustrator", "adobe after effects", "after effects",
    "adobe premier pro", "premier pro", "adobe indesign", "indesign",
    "user research", "user experience", "git", "github", "docker", "aws",
    "linux", "excel", "power bi", "tableau", "english", "communication",
    "writing", "microsoft office", "leadership", "customer management",
    "social media",
]


def extract_info(text, pdf_path, fallback_name):
    """Simple regex-based replacement for pyresparser."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone = re.search(r"(\+?\d[\d\s\-()]{8,15}\d)", text)

    name = ""
    for line in lines[:10]:
        if "@" in line or re.search(r"\d", line) or not (3 <= len(line) <= 40):
            continue
        if len(line.split()) <= 4:
            name = line.title()
            break

    degrees = re.findall(
        r"\b(B\.?\s?Tech|B\.?E\.?|M\.?\s?Tech|M\.?E\.?|MBA|B\.?Sc|M\.?Sc|BCA|MCA|"
        r"Bachelor[^\n,]{0,30}|Master[^\n,]{0,30}|Ph\.?D)\b", text, re.I)

    lower = text.lower()
    skills = []
    for s in KNOWN_SKILLS:
        pattern = r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9+#])"
        if re.search(pattern, lower):
            skills.append(s)

    return {
        "name": name or fallback_name or "Candidate",
        "email": email.group(0) if email else "Not found",
        "mobile_number": phone.group(0).strip() if phone else "Not found",
        "degree": [d.strip() for d in degrees][:3],
        "skills": skills,
        "no_of_pages": count_pages(pdf_path),
    }


def course_recommender(course_list, key):
    st.subheader("**Courses & Certificates Recommendations 👨‍🎓**")
    no_of_reco = st.slider("Choose Number of Course Recommendations:", 1, 10, 5, key=key)
    courses = list(course_list)
    random.Random(key).shuffle(courses)  # stable order between reruns
    rec = []
    for i, (c_name, c_link) in enumerate(courses[:no_of_reco], start=1):
        st.markdown(f"({i}) [{c_name}]({c_link})")
        rec.append(c_name)
    return rec


def get_location():
    blank = ("", "", "", "")
    if geocoder is None:
        return blank
    try:
        latlong = geocoder.ip("me").latlng
        if not latlong:
            return blank
        city = state = country = ""
        if Nominatim is not None:
            loc = Nominatim(user_agent="resume-analyzer", timeout=5).reverse(latlong, language="en")
            addr = loc.raw.get("address", {}) if loc else {}
            city = addr.get("city") or addr.get("town") or addr.get("village", "")
            state = addr.get("state", "")
            country = addr.get("country", "")
        return latlong, city, state, country
    except Exception:
        return blank


def pie(series, title, colors=None):
    counts = series.astype(str).value_counts()
    fig = px.pie(values=counts.values, names=counts.index, title=title,
                 color_discrete_sequence=colors)
    st.plotly_chart(fig)


def msg(text, color):
    st.markdown(f"<h5 style='text-align:left;color:{color};'>{text}</h5>",
                unsafe_allow_html=True)


###### ATS score and Job Description match ######

ACTION_VERBS = [
    "developed", "designed", "built", "created", "implemented", "led", "managed",
    "improved", "increased", "reduced", "analyzed", "automated", "optimized",
    "launched", "delivered", "achieved", "collaborated", "deployed", "engineered",
    "organized", "coordinated", "trained", "researched", "maintained", "tested",
]

STOPWORDS = set("""a an the and or of to in for on with at by from as is are was were be been
this that these those it its we you your our their will can should must may have has had
job role work working team teams ability strong good great excellent experience years year
required requirements responsibilities candidate looking skills knowledge understanding
including such using use etc also more than into across able need needs plus preferred
""".split())


def ats_analysis(text, data):
    """Return (score, list of (ok, points_earned, points_max, message))."""
    lower = text.lower()
    words = re.findall(r"[a-zA-Z]+", text)
    results = []

    def add(earned, maximum, good, bad):
        results.append((earned == maximum, earned, maximum, good if earned else bad))

    # Contact details (25)
    add(10 if data["email"] != "Not found" else 0, 10,
        "Email address found", "Add a professional email address")
    add(10 if data["mobile_number"] != "Not found" else 0, 10,
        "Phone number found", "Add a phone number")
    add(5 if re.search(r"linkedin\.com|github\.com", lower) else 0, 5,
        "LinkedIn/GitHub link found", "Add your LinkedIn or GitHub link")

    # Length (10)
    pages = data["no_of_pages"]
    add(10 if pages <= 2 else 5 if pages == 3 else 0, 10,
        f"Good length ({pages} page(s))",
        f"Resume is {pages} pages, keep it to 1-2 pages")

    # Action verbs (15)
    verbs = {v for v in ACTION_VERBS if re.search(r"\b" + v + r"\b", lower)}
    add(15 if len(verbs) >= 5 else 8 if len(verbs) >= 2 else 0, 15,
        f"Uses strong action verbs ({len(verbs)} found)",
        "Start bullet points with action verbs like developed, built, improved")

    # Measurable results (15)
    numbers = re.findall(r"\d+\s?%|\b\d{2,}\+?\b", text)
    add(15 if len(numbers) >= 5 else 8 if len(numbers) >= 2 else 0, 15,
        "Includes measurable results/numbers",
        "Add numbers to show impact, e.g. 'improved speed by 30%'")

    # Enough readable text (10)
    add(10 if len(words) >= 300 else 5 if len(words) >= 150 else 0, 10,
        f"Enough readable text ({len(words)} words)",
        "Very little text found. Avoid images/scans and add more detail")

    # Standard sections (15)
    for label, keys in [("Education", ["education"]),
                        ("Experience or Projects", ["experience", "project"]),
                        ("Skills", ["skill"])]:
        add(5 if has_any(text, keys) else 0, 5,
            f"{label} section found", f"Add a clear '{label}' heading")

    # Number of skills (10)
    n = len(data["skills"])
    add(10 if n >= 8 else 5 if n >= 4 else 0, 10,
        f"{n} skills detected", "List more relevant skills (aim for 8 or more)")

    score = sum(r[1] for r in results)
    return score, results


def jd_match(resume_text, jd_text):
    """Compare resume with a pasted job description."""
    jd_lower = jd_text.lower()
    keywords = []
    for s in KNOWN_SKILLS:
        if re.search(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9+#])", jd_lower):
            keywords.append(s)

    freq = {}
    for w in re.findall(r"[a-z][a-z+#.]{3,}", jd_lower):
        if w not in STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    common = [w for w, c in sorted(freq.items(), key=lambda x: -x[1]) if c >= 2][:20]
    for w in common:
        if w not in keywords:
            keywords.append(w)

    resume_lower = resume_text.lower()
    matched = [k for k in keywords
               if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9+#])", resume_lower)]
    missing = [k for k in keywords if k not in matched]
    pct = round(100 * len(matched) / len(keywords)) if keywords else 0
    return pct, matched, missing


###### Keyword lists for field prediction ######

FIELDS = [
    ("Data Science",
     ["tensorflow", "keras", "pytorch", "machine learning", "deep learning", "flask", "streamlit"],
     ["Data Visualization", "Predictive Analysis", "Statistical Modeling", "Data Mining",
      "Clustering & Classification", "Data Analytics", "Quantitative Analysis", "Web Scraping",
      "ML Algorithms", "Keras", "Pytorch", "Probability", "Scikit-learn", "Tensorflow",
      "Flask", "Streamlit"], ds_course),
    ("Web Development",
     ["react", "django", "node js", "react js", "php", "laravel", "magento", "wordpress",
      "javascript", "angular js", "c#", "asp.net", "flask"],
     ["React", "Django", "Node JS", "React JS", "php", "laravel", "Magento", "wordpress",
      "Javascript", "Angular JS", "c#", "Flask", "SDK"], web_course),
    ("Android Development",
     ["android", "android development", "flutter", "kotlin", "xml", "kivy"],
     ["Android", "Android development", "Flutter", "Kotlin", "XML", "Java", "Kivy", "GIT",
      "SDK", "SQLite"], android_course),
    ("IOS Development",
     ["ios", "ios development", "swift", "cocoa", "cocoa touch", "xcode"],
     ["IOS", "IOS Development", "Swift", "Cocoa", "Cocoa Touch", "Xcode", "Objective-C",
      "SQLite", "Plist", "StoreKit", "UI-Kit", "AV Foundation", "Auto-Layout"], ios_course),
    ("UI-UX Development",
     ["ux", "adobe xd", "figma", "zeplin", "balsamiq", "ui", "prototyping", "wireframes",
      "wireframe", "adobe photoshop", "photoshop", "editing", "adobe illustrator",
      "illustrator", "adobe after effects", "after effects", "adobe premier pro",
      "premier pro", "adobe indesign", "indesign", "user research", "user experience"],
     ["UI", "User Experience", "Adobe XD", "Figma", "Zeplin", "Balsamiq", "Prototyping",
      "Wireframes", "Storyframes", "Adobe Photoshop", "Editing", "Illustrator",
      "After Effects", "Premier Pro", "Indesign", "Wireframe", "Solid", "Grasp",
      "User Research"], uiux_course),
]

# (label, keywords, points, good message, missing message)
SCORE_ITEMS = [
    ("Objective/Summary", ["objective", "summary"], 6,
     "You have added Objective/Summary",
     "Please add your career objective, it will give your career intention to the recruiters."),
    ("Education", ["education", "school", "college"], 12,
     "You have added Education Details",
     "Please add Education. It will give your qualification level to the recruiter."),
    ("Experience", ["experience"], 16,
     "You have added Experience",
     "Please add Experience. It will help you to stand out from the crowd."),
    ("Internships", ["internship"], 6,
     "You have added Internships",
     "Please add Internships. It will help you to stand out from the crowd."),
    ("Skills", ["skill"], 7,
     "You have added Skills", "Please add Skills. It will help you a lot."),
    ("Hobbies", ["hobbies"], 4,
     "You have added your Hobbies",
     "Please add Hobbies. It will show your personality to the recruiters."),
    ("Interests", ["interests"], 5,
     "You have added your Interest",
     "Please add Interest. It will show your interest other than the job."),
    ("Achievements", ["achievements"], 13,
     "You have added your Achievements",
     "Please add Achievements. It will show that you are capable for the required position."),
    ("Certifications", ["certification"], 12,
     "You have added your Certifications",
     "Please add Certifications. It will show that you have done some specialization."),
    ("Projects", ["project"], 19,
     "You have added your Projects",
     "Please add Projects. It will show that you have done work related to the position."),
]


###### Main app ######

def run():
    logo = os.path.join(BASE_DIR, "Logo", "RESUME.png")
    if os.path.exists(logo):
        st.image(Image.open(logo))
    else:
        st.title("AI Resume Analyzer")

    st.sidebar.markdown("# Choose Something...")
    choice = st.sidebar.selectbox("Choose among the given options:",
                                  ["User", "Feedback", "About", "Admin"])
    st.sidebar.markdown("<b>Built with 🤍 by D Nageshwari </b>", unsafe_allow_html=True)

    ###### USER ######
    if choice == "User":
        act_name = st.text_input("Name*")
        act_mail = st.text_input("Mail*")
        act_mob = st.text_input("Mobile Number*")

        st.markdown("<h5 style='text-align:left;color:#021659;'>Upload Your Resume, "
                    "And Get Smart Recommendations</h5>", unsafe_allow_html=True)
        pdf_file = st.file_uploader("Choose your Resume", type=["pdf"])
        if pdf_file is None:
            return

        save_path = os.path.join(UPLOAD_DIR, os.path.basename(pdf_file.name))
        with open(save_path, "wb") as f:
            f.write(pdf_file.getbuffer())
        show_pdf(save_path)

        try:
            resume_text = extract_text(save_path)
            data = extract_info(resume_text, save_path, act_name)
        except Exception as e:
            st.error(f"Could not read this PDF: {e}")
            return
        if not resume_text.strip():
            st.error("No text found in this PDF (it may be a scanned image).")
            return

        st.header("**Resume Analysis 🤘**")
        st.success("Hello " + data["name"])
        st.subheader("**Your Basic info 👀**")
        st.text("Name: " + data["name"])
        st.text("Email: " + data["email"])
        st.text("Contact: " + data["mobile_number"])
        st.text("Degree: " + str(data["degree"]))
        st.text("Resume pages: " + str(data["no_of_pages"]))

        # Experience level
        if has_any(resume_text, ["internship"]):
            cand_level = "Intermediate"
            msg("You are at intermediate level!", "#1ed760")
        elif has_any(resume_text, ["experience"]):
            cand_level = "Experienced"
            msg("You are at experience level!", "#fba171")
        else:
            cand_level = "Fresher"
            msg("You are at Fresher level!", "#d73b5c")

        # Skills
        st.subheader("**Skills Recommendation 💡**")
        st_tags(label="### Your Current Skills",
                text="See our skills recommendation below",
                value=data["skills"], key="skills_current")

        user_skills = {s.lower() for s in data["skills"]}
        best = max(FIELDS, key=lambda f: len(user_skills & set(f[1])))
        reco_field, recommended_skills, rec_course = "NA", ["No Recommendations"], "Not Available"

        if user_skills & set(best[1]):
            reco_field, _, recommended_skills, course_list = best
            st.success(f"** Our analysis says you are looking for {reco_field} Jobs **")
            st_tags(label="### Recommended skills for you.",
                    text="Recommended skills generated from System",
                    value=recommended_skills, key="skills_reco")
            msg("Adding these skills to your resume will boost🚀 the chances of getting a Job💼",
                "#1ed760")
            rec_course = course_recommender(course_list, key="course_slider")
        else:
            st.warning("** Currently our tool only predicts and recommends for Data Science, "
                       "Web, Android, IOS and UI/UX Development **")
            msg("Maybe Available in Future Updates", "#092851")

        # Resume score
        st.subheader("**Resume Tips & Ideas 🥂**")
        resume_score = 0
        for _, words, points, good, bad in SCORE_ITEMS:
            if has_any(resume_text, words):
                resume_score += points
                msg("[+] Awesome! " + good, "#1ed760")
            else:
                msg("[-] " + bad, "#888888")

        st.subheader("**Resume Score 📝**")
        st.markdown("<style>.stProgress > div > div > div > div "
                    "{background-color: #d73b5c;}</style>", unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(resume_score):
            bar.progress(i + 1)
            time.sleep(0.01)
        st.success("** Your Resume Writing Score: " + str(resume_score) + "**")
        st.warning("** Note: This score is calculated based on the content that you have in your Resume. **")

        save_key = f"{pdf_file.name}_{pdf_file.size}_{act_mail}"

        # ATS-style score
        st.subheader("**ATS Score 🤖**")
        ats_score, ats_results = ats_analysis(resume_text, data)
        st.progress(ats_score / 100)
        if ats_score >= 75:
            st.success(f"** ATS Score: {ats_score}/100 (Good, likely to pass ATS screening) **")
        elif ats_score >= 50:
            st.warning(f"** ATS Score: {ats_score}/100 (Average, some improvements needed) **")
        else:
            st.error(f"** ATS Score: {ats_score}/100 (Low, follow the tips below) **")
        for ok, earned, maximum, text in ats_results:
            msg(f"[{'+' if ok else '-'}] {text} ({earned}/{maximum})",
                "#1ed760" if ok else "#d73b5c")
        st.caption("ATS = Applicant Tracking System. This is an estimate based on common "
                   "ATS rules, not the score from any specific company's software.")

        # Job description match
        st.subheader("**Job Description Match 🎯**")
        jd_text = st.text_area("Paste a job description to see how well your resume matches it",
                               height=200, key="jd_text")
        if jd_text.strip():
            pct, matched, missing = jd_match(resume_text, jd_text)
            if pct >= 60:
                st.success(f"** Keyword match: {pct}% **")
            else:
                st.warning(f"** Keyword match: {pct}% **")
            st.progress(pct / 100)
            jd_key = f"{save_key}_{pct}"
            # only update the row that belongs to THIS uploaded resume
            if (st.session_state.get("saved_key") == save_key
                    and st.session_state.get("jd_saved") != jd_key):
                update_jd_match(st.session_state["row_id"], pct)
                st.session_state["jd_saved"] = jd_key
            st.markdown("**Matched keywords:** " + (", ".join(matched) or "None"))
            st.markdown("**Missing keywords (add these if you really have the skill):** "
                        + (", ".join(missing) or "None"))

        # Save once per uploaded file (avoid duplicates on reruns)
        if st.session_state.get("saved_key") != save_key:
            host_name = socket.gethostname()
            try:
                ip_add = socket.gethostbyname(host_name)
            except Exception:
                ip_add = "unknown"
            try:
                dev_user = getpass.getuser()
            except Exception:
                dev_user = "unknown"
            latlong, city, state, country = get_location()
            row_id = insert_data(secrets.token_urlsafe(12), ip_add, host_name, dev_user,
                        platform.system() + " " + platform.release(),
                        latlong, city, state, country,
                        act_name, act_mail, act_mob,
                        data["name"], data["email"], resume_score, now_stamp(),
                        data["no_of_pages"], reco_field, cand_level,
                        data["skills"], recommended_skills, rec_course,
                        pdf_file.name, ats_score)
            st.session_state["row_id"] = row_id
            st.session_state["saved_key"] = save_key
            st.balloons()

        if resume_videos:
            st.header("**Bonus Video for Resume Writing Tips💡**")
            st.video(random.Random(save_key).choice(resume_videos))
        if interview_videos:
            st.header("**Bonus Video for Interview Tips💡**")
            st.video(random.Random(save_key + "i").choice(interview_videos))

    ###### FEEDBACK ######
    elif choice == "Feedback":
        with st.form("my_form"):
            st.write("Feedback form")
            feed_name = st.text_input("Name")
            feed_email = st.text_input("Email")
            feed_score = st.slider("Rate Us From 1 - 5", 1, 5, 3)
            comments = st.text_input("Comments")
            if st.form_submit_button("Submit"):
                insertf_data(feed_name, feed_email, feed_score, comments, now_stamp())
                st.success("Thanks! Your Feedback was recorded.")
                st.balloons()

        fb = pd.read_sql("SELECT * FROM user_feedback", conn)
        if fb.empty:
            st.info("No feedback yet.")
        else:
            st.subheader("**Past User Rating's**")
            pie(fb["feed_score"], "Chart of User Rating Score From 1 - 5",
                px.colors.sequential.Aggrnyl)
            st.subheader("**User Comment's**")
            st.dataframe(fb[["feed_name", "comments"]].rename(
                columns={"feed_name": "User", "comments": "Comment"}))

    ###### ABOUT ######
    elif choice == "About":
        st.subheader("**About The Tool - AI RESUME ANALYZER**")
        st.markdown("""
        <p align='justify'>
        A tool which parses information from a resume, finds keywords, groups them into
        sectors and shows recommendations, predictions and analytics based on keyword matching.
        </p>
        <p align="justify">
        <b>User -</b> choose User in the sidebar, fill the fields and upload your resume as PDF.<br/>
        <b>Feedback -</b> share your feedback about the tool.<br/>
        <b>Admin -</b> log in to view all collected data and charts.
        </p>""", unsafe_allow_html=True)

    ###### ADMIN ######
    else:
        st.success("Welcome to Admin Side")
        if not st.session_state.get("admin_ok"):
            tab_login, tab_reg = st.tabs(["🔐 Login", "📝 Register"])

            with tab_login:
                user = st.text_input("Username", key="login_user")
                pw = st.text_input("Password", type="password", key="login_pw")
                if st.button("Login"):
                    who = check_admin_login(user, pw)
                    if who:
                        st.session_state["admin_ok"] = True
                        st.session_state["admin_name"] = who
                        st.rerun()
                    else:
                        st.error("Wrong ID & Password Provided")

            with tab_reg:
                st.caption("Create a new admin account. You need the admin registration code.")
                r_name = st.text_input("Full Name", key="reg_name")
                r_email = st.text_input("Email", key="reg_email")
                r_user = st.text_input("Choose a Username", key="reg_user")
                r_pw = st.text_input("Password", type="password", key="reg_pw")
                r_pw2 = st.text_input("Confirm Password", type="password", key="reg_pw2")
                r_code = st.text_input("Admin Registration Code", type="password", key="reg_code")
                if st.button("Register"):
                    if not (r_user and r_pw and r_code):
                        st.error("Username, password and registration code are required.")
                    elif r_pw != r_pw2:
                        st.error("Passwords do not match.")
                    elif not hmac.compare_digest(r_code, ADMIN_REG_CODE):
                        st.error("Invalid admin registration code.")
                    else:
                        ok, message = register_admin(r_user, r_name, r_email, r_pw)
                        if ok:
                            st.success(message)
                        else:
                            st.error(message)
            return

        if st.button("Logout"):
            st.session_state["admin_ok"] = False
            st.rerun()

        df = pd.read_sql("SELECT * FROM user_data", conn)
        st.success("Welcome %s ! Total %d User's Have Used Our Tool : )"
                   % (st.session_state.get("admin_name", "Admin"), len(df)))
        if not df.empty:
            ats = pd.to_numeric(df["ats_score"], errors="coerce")
            jd = pd.to_numeric(df["jd_match"], errors="coerce")
            c1, c2, c3 = st.columns(3)
            c1.metric("Average Resume Score",
                      round(pd.to_numeric(df["resume_score"], errors="coerce").mean(), 1))
            c2.metric("Average ATS Score", round(ats.mean(), 1) if ats.notna().any() else "N/A")
            c3.metric("Average JD Match", f"{round(jd.mean(), 1)}%" if jd.notna().any() else "N/A")

        st.header("**User's Data**")
        st.dataframe(df)
        st.markdown(get_csv_download_link(df, "User_Data.csv", "Download Report"),
                    unsafe_allow_html=True)

        fb = pd.read_sql("SELECT * FROM user_feedback", conn)
        st.header("**User's Feedback Data**")
        st.dataframe(fb)

        if not fb.empty:
            st.subheader("**User Rating's**")
            pie(fb["feed_score"], "Chart of User Rating Score From 1 - 5 🤗",
                px.colors.sequential.Aggrnyl)

        if not df.empty:
            charts = [
                ("Predicted_Field", "Pie-Chart for Predicted Field Recommendation",
                 "Predicted Field according to the Skills 👽", px.colors.sequential.Aggrnyl_r),
                ("User_level", "Pie-Chart for User's Experienced Level",
                 "Pie-Chart 📈 for User's 👨‍💻 Experienced Level", px.colors.sequential.RdBu),
                ("resume_score", "Pie-Chart for Resume Score",
                 "From 1 to 100 💯", px.colors.sequential.Agsunset),
                ("ip_add", "Pie-Chart for Users App Used Count",
                 "Usage Based On IP Address 👥", px.colors.sequential.matter_r),
                ("city", "Pie-Chart for City", "Usage Based On City 🌆",
                 px.colors.sequential.Jet),
                ("state", "Pie-Chart for State", "Usage Based on State 🚉",
                 px.colors.sequential.PuBu_r),
                ("country", "Pie-Chart for Country", "Usage Based on Country 🌏",
                 px.colors.sequential.Purpor_r),
            ]
            if pd.to_numeric(df["ats_score"], errors="coerce").notna().any():
                st.subheader("**ATS Score Distribution**")
                bands = pd.cut(pd.to_numeric(df["ats_score"], errors="coerce"),
                               bins=[-1, 49, 74, 100],
                               labels=["Low (0-49)", "Average (50-74)", "Good (75-100)"])
                pie(bands.dropna(), "ATS Score Bands", px.colors.sequential.Aggrnyl)
            for col, header, title, colors in charts:
                st.subheader("**" + header + "**")
                pie(df[col].replace("", "Unknown"), title, colors)


run()