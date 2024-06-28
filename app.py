import streamlit as st
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import sqlite3
import warnings
from datetime import datetime
import pytz
import re

# Suppress specific FutureWarning
warnings.filterwarnings("ignore", category=FutureWarning, module="pyarrow.pandas_compat")

# Initial setup
st.title("Confirmation Form for Invoice Delivery and General Information")
st.write("Dear Madam/Sir, Here is the confirmation form for sending invoices and general information announcements from Sekolah Harapan Bangsa.")
st.write("Please ensure that the WA (WhatsApp) number and email formats are correct and currently active.")
st.write("If you wish to receive invoices separately for both Father and Mother with different WA numbers and emails, please fill out the form twice alternately.")

# Initialize SQLite database
conn = sqlite3.connect('responses.db')
c = conn.cursor()

# Check if 'responses' table exists, and create if it doesn't
c.execute('''
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grade TEXT,
        student_name TEXT,
        parent_name TEXT,
        wa_active_parent TEXT,
        email_active_parent TEXT,
        signature BLOB,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# Form fields
if 'grade' not in st.session_state:
    st.session_state.grade = ''
if 'student_name' not in st.session_state:
    st.session_state.student_name = ''
if 'parent_name' not in st.session_state:
    st.session_state.parent_name = ''
if 'wa_active_parent' not in st.session_state:
    st.session_state.wa_active_parent = ''
if 'email_active_parent' not in st.session_state:
    st.session_state.email_active_parent = ''

grade = st.selectbox("Grade", ["Grade 7A", "Grade 7B", "Grade 8A", "Grade 8B", "Grade 9A", "Grade 9B", "Grade 10", "Grade 11", "Grade 12"], index=0)
student_name = st.text_input("Student Name", st.session_state.student_name)
parent_name = st.text_input("Parent Name", st.session_state.parent_name)
wa_active_parent = st.text_input("WA Active Parent", st.session_state.wa_active_parent)
email_active_parent = st.text_input("Email Active Parent", st.session_state.email_active_parent)

# Signature
st.write("Signature:")
canvas_result = st_canvas(
    stroke_width=2,
    stroke_color="#000000",
    background_color="#FFFFFF",
    height=150,
    width=400,
    drawing_mode="freedraw",
    key="canvas"
)

# Email setup
your_name = "Sekolah Harapan Bangsa"
your_email = "shsmodernhill@shb.sch.id"
your_password = "jvvmdgxgdyqflcrf"

# Form validation
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def is_valid_phone(phone):
    return re.match(r"^\+?1?\d{9,15}$", phone)

if st.button("Submit"):
    # Validation checks
    if not student_name or not parent_name or not wa_active_parent or not email_active_parent:
        st.error("Please fill in all the required fields.")
    elif not is_valid_phone(wa_active_parent):
        st.error("Please enter a valid phone number in the format: +1234567890.")
    elif not is_valid_email(email_active_parent):
        st.error("Please enter a valid email address.")
    else:
        # Save signature
        signature_img = None
        if canvas_result.image_data is not None:
            img = Image.fromarray(canvas_result.image_data)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            signature_img = buf.getvalue()

        # Insert data into SQLite database
        c.execute('''
            INSERT INTO responses (grade, student_name, parent_name, wa_active_parent, email_active_parent, signature, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        ''', (grade, student_name, parent_name, wa_active_parent, email_active_parent, signature_img))
        conn.commit()

        # Generate PDF using template
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        
        # Current timestamp
        tz = pytz.timezone('Asia/Jakarta')
        current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

        can.drawString(100, 675, "Menyatakan dengan ini bahwa:")
        can.drawString(100, 650, f"Nama Peserta Didik           : {student_name}")
        can.drawString(100, 625, f"Kelas                                  : {grade}")
        can.drawString(100, 600, f"Nama Orang Tua               : {parent_name}")
        can.drawString(100, 575, f"WA aktif Orang Tua/Wali   : {wa_active_parent}")
        can.drawString(100, 550, f"Email aktif Orang Tua/Wali: {email_active_parent}")
        can.drawString(100, 525, f"Timestamp: {current_time}")
        can.drawString(100, 500, "Demikian konfirmasi dari kami. Terima Kasih.")
        can.drawString(100, 475, "Hormat Kami,")
        
        if signature_img:
            img = Image.open(io.BytesIO(signature_img))
            img.save("temp_sig.png")
            can.drawImage("temp_sig.png", 100, 400, width=200, height=50)

        can.drawString(100, 350, "Orang Tua/Wali")
        can.save()

        packet.seek(0)
        new_pdf = PdfReader(packet)
        existing_pdf = PdfReader(open("konfirmasi.pdf", "rb"))
        output = PdfWriter()
        page = existing_pdf.pages[0]
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)

        pdf_buffer = io.BytesIO()
        output.write(pdf_buffer)
        pdf_buffer.seek(0)
        pdf_file = f"{student_name}_form.pdf"

        # Send email
        msg = MIMEMultipart()
        msg["From"] = your_email
        msg["To"] = email_active_parent
        msg["Subject"] = "Form Email and WA Number Submission Confirmation"

        body = "Dear Parent/Guardian, here is your confirmation email and Whatsapp number, respectively. Thanks. Please find the attached PDF for your form submission."
        msg.attach(MIMEText(body, "plain"))

        part = MIMEApplication(pdf_buffer.read(), Name=pdf_file)
        part["Content-Disposition"] = f'attachment; filename="{pdf_file}"'
        msg.attach(part)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(your_email, your_password)
            server.send_message(msg)

        st.success("Form submitted successfully! Please kindly check your email. Thanks")
        
        # Clear form fields
        st.session_state.grade = ''
        st.session_state.student_name = ''
        st.session_state.parent_name = ''
        st.session_state.wa_active_parent = ''
        st.session_state.email_active_parent = ''

# Admin page
st.sidebar.title("Admin Login")
admin_username = st.sidebar.text_input("Username")
admin_password = st.sidebar.text_input("Password", type="password")

if st.sidebar.button("Login"):
    if admin_username == "Admin" and admin_password == "123456":
        st.session_state.admin_logged_in = True

if 'admin_logged_in' in st.session_state and st.session_state.admin_logged_in:
    st.sidebar.success("Logged in as Admin")

    if st.sidebar.button("Logout"):
        st.session_state.admin_logged_in = False
        st.sidebar.info("Logged out")

    # Display admin controls
    st.title("Admin Page")
    st.write("Download all form responses as an Excel file.")
    
    # Fetch data from SQLite database
    c.execute('SELECT id, grade, student_name, parent_name, wa_active_parent, email_active_parent, timestamp FROM responses')
    rows = c.fetchall()
    if not rows:
        st.write("No data available.")
    else:
        df = pd.DataFrame(rows, columns=["ID", "Grade", "Student Name", "Parent Name", "WA Active Parent", "Email Active Parent", "Timestamp"])
        st.write(df)
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        st.download_button(
            label="Download Excel",
            data=excel_buffer,
            file_name="form_responses.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Admin CRUD functionalities
        st.subheader("Edit/Delete Responses")

        selected_id = st.selectbox("Select Response ID to Edit/Delete", df["ID"])
        selected_row = df[df["ID"] == selected_id]

        if not selected_row.empty:
            st.write(selected_row)

            new_grade = st.selectbox("New Grade", ["Grade 7A", "Grade 7B", "Grade 8A", "Grade 8B", "Grade 9A", "Grade 9B", "Grade 10", "Grade 11", "Grade 12"], index=0)
            new_student_name = st.text_input("New Student Name", selected_row["Student Name"].values[0])
            new_parent_name = st.text_input("New Parent Name", selected_row["Parent Name"].values[0])
            new_wa_active_parent = st.text_input("New WA Active Parent", selected_row["WA Active Parent"].values[0])
            new_email_active_parent = st.text_input("New Email Active Parent", selected_row["Email Active Parent"].values[0])

            if st.button("Update"):
                c.execute('''
                    UPDATE responses
                    SET grade = ?, student_name = ?, parent_name = ?, wa_active_parent = ?, email_active_parent = ?
                    WHERE id = ?
                ''', (new_grade, new_student_name, new_parent_name, new_wa_active_parent, new_email_active_parent, selected_id))
                conn.commit()
                st.success("Response updated successfully!")

            if st.button("Delete"):
                c.execute('''
                    DELETE FROM responses WHERE id = ?
                ''', (selected_id,))
                conn.commit()
                st.success("Response deleted successfully!")
else:
    st.sidebar.error("Invalid username or password")

# Close SQLite connection
conn.close()