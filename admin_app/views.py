from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
import firebase_admin
from firebase_admin import credentials, firestore, messaging
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
import base64
import datetime
import pytz
import io
import uuid, os

# Check if Firebase is already initialized
# if not firebase_admin._apps:
#     # Initialize Firebase only if not already initialized
#     cred = credentials.Certificate('admin_app/firebase/service-account.json')
#     firebase_admin.initialize_app(cred, {
#     'httpTimeout': 120  # 120 seconds timeout, you can increase as needed
# })

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure Firebase is initialized only once
if not firebase_admin._apps:
    # Load Firebase credentials from the environment variables
    cred = credentials.Certificate({
        "type": os.getenv("FIREBASE_TYPE"),
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace(r'\n', '\n'),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
        "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
        "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
        "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN"),
    })

    # Initialize the Firebase app
    firebase_admin.initialize_app(cred)
    
# Now you can use Firebase as usual
db = firestore.client()


def admin_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        if email == 'w@w.com' and password == '123456':
            request.session['admin'] = True
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials')
    return render(request, 'login.html')


def admin_logout(request):
    request.session.flush()
    return redirect('login')


def dashboard(request):
    if not request.session.get('admin'):
        return redirect('login')
    
    # Fetching all users from the 'users' collection
    users_ref = db.collection('users')
    users = users_ref.stream()
    total_users = sum(1 for user in users)  # Counting total users

    # Pass data to the template
    context = {
        'total_users': total_users,
        'users': users_ref.stream()  # Pass all user data to display in the dashboard
    }

    return render(request, 'dashboard.html', context)

def generate_qr(request):
    if not request.session.get('admin'):
        return redirect('login')
    
    if request.method == 'POST':
        count = int(request.POST.get('count'))
        qr_data = []
        base_url = "https://sudo-be.onrender.com/send-notification/"
        
        for _ in range(count):
            # Generate a shorter user ID
            user_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:8]  # Only first 8 characters
            user_data = {
                'createdAt': datetime.datetime.now(),
                'deviceId': '',
                'emailAddress': '',
                'enableIdCheck': True,
                'fcmToken': '',
                'firstname': '',
                'lastName': '',
                'location': '',
                'mobileNumber': '',
                'profileLogo': 'profileLogo',
                'role': 0,
                'userId': user_id,
            }
            db.collection('users').document(user_id).set(user_data)

            # Generate QR code with the dynamic URL
            dynamic_url = f"{base_url}{user_id}"
            qr_code = qrcode.make(dynamic_url)

            # Convert QR code to base64
            buffer = BytesIO()
            qr_code.save(buffer, format="PNG")
            buffer.seek(0)
            qr_code_base64 = base64.b64encode(buffer.read()).decode('utf-8')

            qr_data.append({'userId': user_id, 'qr_code_base64': qr_code_base64})

        request.session['qr_data'] = [
            {'userId': item['userId']} for item in qr_data
        ]  # Save only IDs for PDF generation

        return render(request, 'generate_qr.html', {'qr_data': qr_data})

    return render(request, 'generate_qr.html')



def download_qr_pdf(request):
    if not request.session.get('admin') or 'qr_data' not in request.session:
        return redirect('login')

    qr_data = request.session.pop('qr_data')  # Retrieve and clear session data
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="qr_codes.pdf"'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    # Title and date styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="Title", fontSize=24, alignment=1, fontName="Helvetica-Bold", spaceAfter=12, textColor=colors.black)
    date_style = ParagraphStyle(name="Date", fontSize=12, alignment=1, fontName="Helvetica", spaceBefore=18, spaceAfter=24, textColor=colors.darkgrey)

    # Title and date
    title = Paragraph("Generated QR Codes", title_style)
    elements.append(title)
    ist = pytz.timezone('Asia/Kolkata')
    current_datetime = datetime.datetime.now(ist)
    date_time_string = current_datetime.strftime("%A, %B %d, %Y - %I:%M %p")
    date_time_paragraph = Paragraph(f"Created on: {date_time_string}", date_style)
    elements.append(date_time_paragraph)
    elements.append(Spacer(1, 18))

    # Generate QR codes with dynamic URLs
    base_url = "https://sudo-be.onrender.com/send-notification/"
    data = []
    row = []

    for index, qr in enumerate(qr_data):
        # Create a QR code with the dynamic URL
        dynamic_url = f"{base_url}{qr['userId']}"
        qr_code = qrcode.make(dynamic_url)

        # Convert the QR code to an image
        qr_code_buffer = BytesIO()
        qr_code.save(qr_code_buffer, format='PNG')
        qr_code_buffer.seek(0)
        qr_code_base64 = base64.b64encode(qr_code_buffer.read()).decode('utf-8')

        qr_image = Image(BytesIO(base64.b64decode(qr_code_base64)), width=100, height=100)
        qr_image.hAlign = 'CENTER'

        # User ID below the QR code
        user_id_paragraph = Paragraph(f"<b>{qr['userId']}</b>", styles['BodyText'])

        # Combine QR code and User ID in a column
        column = [qr_image, user_id_paragraph]
        row.append(column)

        if len(row) == 2:  # Add two columns per row
            data.append(row)
            row = []

    if row:  # Add remaining columns if any
        data.append(row)

    # Create a table for the QR code and user IDs
    table = Table(data, colWidths=[doc.width * 0.5] * 2)
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
    ]))

    elements.append(table)
    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response



def register_user(request):
    if not request.session.get('admin'):
        return redirect('login')
    users = db.collection('users').stream()
    user_list = [{'userId': user.id, **user.to_dict()} for user in users]
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        updated_data = {
            'firstname': request.POST.get('firstname'),
            'lastName': request.POST.get('lastname'),
            'emailAddress': request.POST.get('email'),
            'mobileNumber': request.POST.get('mobile'),
            'location': request.POST.get('location'),
        }
        db.collection('users').document(user_id).update(updated_data)
        messages.success(request, 'User updated successfully')
    return render(request, 'register_user.html', {'users': user_list})


def manage_users(request):
    # Ensure the user is an admin
    if not request.session.get('admin'):
        return redirect('login')

    # Connect to Firestore
    db = firestore.client()
    users_ref = db.collection('users')
    users = [doc.to_dict() for doc in users_ref.stream()]

    # Check if the form is submitted to delete users
    if request.method == "POST":
        if 'delete_selected' in request.POST:
            # Get selected user IDs
            selected_user_ids = request.POST.getlist('selected_users')

            if selected_user_ids:
                # Delete selected users from Firestore
                for user_id in selected_user_ids:
                    users_ref.document(user_id).delete()

                messages.success(request, 'Selected users deleted successfully')
            else:
                messages.warning(request, 'No users selected for deletion')

            return redirect('manage_users')

        elif 'delete_single' in request.POST:
            # Get the single user ID to delete
            user_id = request.POST.get('user_id')

            if user_id:
                # Delete the user from Firestore
                users_ref.document(user_id).delete()
                messages.success(request, 'User deleted successfully')
            else:
                messages.warning(request, 'No user selected for deletion')

            return redirect('manage_users')

    return render(request, 'manage_users.html', {'users': users})


def send_notification(request, user_id):
    # Fetch user data from Firestore (assuming you have a method to fetch user data from Firestore)
    user_ref = db.collection('users').document(user_id)
    user_data = user_ref.get()

    if not user_data.exists:
        return render(request, 'send_notification.html', {'error': 'User not found!'})

    user_data = user_data.to_dict()

    # Predefined messages
    messages = {
        "1": "Your car is not locked properly.",
        "2": "Your car alarm is on.",
        "3": "The lights of your car are on.",
        "4": "There is a baby in your car.",
        "5": "Your car is parked on the wrong side.",
        "6": "There is a vehicle in front of your car.",
        "7": "Your vehicle is blocking the way.",
        "8": "The car’s fuel is low.",
        "9": "The car needs maintenance."
    }

    if request.method == 'POST':
        message_key = request.POST.get('message_key')
        if message_key:
            # Get the FCM token from Firestore
            fcm_token = user_data.get('fcmToken')

            # Define the message
            message_body = messages.get(message_key, "No message selected")

            # Create the notification message
            message = messaging.Message(
                notification=messaging.Notification(
                    title="Alert",
                    body=message_body,
                ),
                token=fcm_token,
            )

            # Send the notification
            try:
                response = messaging.send(message)
                return render(request, 'send_notification.html', {
                    'user_data': user_data, 'messages': messages, 'result': 'Notification sent successfully!'
                })
            except Exception as e:
                return render(request, 'send_notification.html', {
                    'user_data': user_data, 'messages': messages, 'error': f'Failed to send notification: {str(e)}'
                })

    return render(request, 'send_notification.html', {'user_data': user_data, 'messages': messages})

