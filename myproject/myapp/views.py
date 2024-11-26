from django.shortcuts import render,redirect
import mysql.connector as sql
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
import re
import requests
from django.conf import settings
from .models import Doctor, Patient, Appointment, WellnessTransaction

@csrf_protect
def registration(request):
    if request.method == "POST":
        us = request.POST.get('username')
        em = request.POST.get('email')
        ps = request.POST.get('password')
        cpass = request.POST.get('cpassword')
 
        errors = {}
 
        # Check if password and confirmation match
        if ps != cpass:
            errors['cpassword_error'] = "Passwords do not match!"
 
        # Password validation checks
        if len(ps) < 6:
            errors['password_error'] = "Password must be at least 6 characters long."
        elif not re.search(r"[!@#$%^&*(),.?\":{}|<>]", ps):
            errors['password_error'] = "Password must include at least one special character."
        elif not (re.search(r"[A-Z]", ps) and re.search(r"[a-z]", ps) and re.search(r"[0-9]", ps)):
            errors['password_error'] = "Password must include uppercase, lowercase, and numbers."
        # If there are errors, re-render the form with error messages
        if errors:
            return render(request, 'registration.html', {'errors': errors})
 
        try:
            # Establishing the connection
            conn = sql.connect(
                host="localhost",
                user="root",
                password="system",
                database="smarthealth"
            )
            cursor = conn.cursor()
 
            # Parameterized query to avoid SQL injection
            comm = "INSERT INTO registration (username, email, password, cpassword) VALUES (%s, %s, %s, %s)"
            cursor.execute(comm, (us, em, ps, cpass))
            conn.commit()
 
            messages.success(request, "Registration successful!")
            return redirect('login')  # Redirect to the login page
 
        except sql.Error as e:
            messages.error(request, f"Error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
 
    return render(request, 'registration.html')


def home(request):
    return render(request,'home.html')

@csrf_protect
def login(request):
    error_message = ""
   
    if request.method == "POST":
        # Connect to the database
        try:
            conn = sql.connect(host="localhost", user="root", password="system", database="smarthealth")
            cursor = conn.cursor()
           
            # Get the data from the form
            username = request.POST.get("username")
            password = request.POST.get("password")
           
            print("Login attempt with username:", username, "and password:", password)  # Debugging print statement
           
            # Retrieve the user data from the database
            query = "SELECT password FROM registration WHERE username = %s"
            cursor.execute(query, (username,))
            result = cursor.fetchone()
           
            if result:
                # If a record is found, check if the password matches
                db_password = result[0]
                print("Password in database:", db_password)
                if db_password == password:
                    request.session['is_logged_in'] = True
                    request.session['username'] = username
                    print("Login successful")  # Debugging print statement
                    # Clear any unread results to avoid errors when closing
                    cursor.fetchall()  # Ensures all results are read
                    return redirect('home')  # Redirect to home page on successful login
                else:
                    error_message = "Invalid password."
            else:
                error_message = "Username not found."
               
        except sql.Error as e:
            print("Database error:", e)
            error_message = "Database error. Please try again later."
        finally:
            # Ensure all results are processed before closing
            cursor.fetchall()  # Clears any remaining results
            if cursor:
                cursor.close()
            if conn:
                conn.close()
   
    # Pass the error message to the template if login fails
    return render(request, 'login.html', {"error_message": error_message})




def logout(request):
    request.session.flush()  # Clears all session data
    return redirect('home') 


 
def dashboard(request):
    # Get counts for doctors, patients, and appointments
    total_doctors = Doctor.objects.count()
    total_patients = Patient.objects.count()
    total_appointments = Appointment.objects.count()  # Count of appointments
 
    # Fetch recent doctors, patients, and appointments with relevant fields
    recent_doctors = Doctor.objects.all().order_by('-id')[:3]  # Limit to the latest 3 doctors
    recent_patients = Patient.objects.all().order_by('-id')[:3]  # Limit to the latest 3 patients
    # recent_appointments = Appointment.objects.all().order_by('-appointment_date')[:3]  # Latest 3 appointments
    recent_appointments = Appointment.objects.all().order_by('-appointment_date')[:3]  # Latest 3 appointments
 
    # Context to pass to the template
    context = {
        'total_doctors': total_doctors,
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'recent_doctors': recent_doctors,
        'recent_patients': recent_patients,
        'recent_appointments': recent_appointments,
    }
 
    return render(request, 'dashboard.html', context)

from django.db.models import Q
 
def wellnesstracking(request):
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        transactions = WellnessTransaction.objects.filter(
            Q(category__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    else:
        transactions = WellnessTransaction.objects.all()
 
    # Pass transactions to the template
    return render(request, 'wellnesstracking.html', {
        'transactions': transactions,
        'search_query': search_query
    })



import json
from django.http import JsonResponse

import google.generativeai as ai

# Function to load the API key from config.json
def load_api_key():
    try:
        with open('config.json') as f:
            config = json.load(f)
            return config.get('API_KEY')
    except FileNotFoundError:
        print("Error: config.json file not found.")
        return None

# Function to generate health advice based on user input
def health_suggestions(request):
    api_key = load_api_key()
    
    if not api_key:
        return JsonResponse({"error": "API key not found."})
    
    ai.configure(api_key=api_key)
    model = ai.GenerativeModel("gemini-pro")
    chat = model.start_chat()
    
    if request.method == "POST":
        user_input = request.POST.get("user_input", "")
        
        # AI prompt for concise suggestions
        prompt = f"Provide 5-10 short points for home remedies or health advice for: {user_input}"

        try:
            response = chat.send_message(prompt)
            suggestions = response.text.strip()

            # Split the response into sentences or lines
            points = suggestions.split("\n")
            points = [point.strip() for point in points if point.strip() != ""]  # Clean up whitespace
            short_points = points[:10]  # Limit to 5-10 points

            # Format the suggestions into bullet points
            bullet_points = [f"• {point}" for point in short_points]

            return JsonResponse({"suggestions": bullet_points})

        except Exception as e:
            return JsonResponse({"error": str(e)})
    
    return render(request, "suggestions.html")
import io
import base64
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg') 

import io
import base64
import matplotlib.pyplot as plt
from django.http import JsonResponse
from django.shortcuts import render
def generate_comparison_graph(data, metric_name, normal_range):
    categories = ["Given", "Normal Range"]
    values = [data, normal_range]
    
    # Create figure for the chart
    plt.figure(figsize=(6, 4))
    plt.bar(categories, values, color=["orange", "green"])
    plt.title(f"{metric_name} Comparison")
    plt.ylabel(metric_name)
    
    # Save plot to a BytesIO object
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png")
    plt.close()
    buffer.seek(0)
    
    # Encode to base64
    graph_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    buffer.close()
    
    return graph_base64

# Function to get recommendation from Google Gemini AI
def get_gemini_ai_recommendation(health_data):
    api_key = load_api_key()
    
    if not api_key:
        return {"error": "API key not found."}
    
    ai.configure(api_key=api_key)
    model = ai.GenerativeModel("gemini-pro")
    chat = model.start_chat()

    # AI prompt for generating health recommendations
    prompt = (f"Based on the following health data, give recommendations if they are not in good health range \n"
              f"Heart Rate: {health_data.get('heart_rate')}\n"
              f"Sleep Hours: {health_data.get('sleep_hours')}\n"
              f"Steps: {health_data.get('steps')}\n"
              f"Calories Burnt: {health_data.get('calories_burnt')}")
    
    try:
        # Send the prompt to the AI model for health recommendations
        response = chat.send_message(prompt)
        recommendations = response.text.strip()

        # Split the response into bullet points
        points = recommendations.split("\n")
        points = [point.strip() for point in points if point.strip() != ""]
        short_points = points[:10]  # Limit to 5-10 points
        bullet_points = [f"• {point}" for point in short_points]
        
        return bullet_points

    except Exception as e:
        return {"error": str(e)}

def healthinsights(request):
    if request.method == "POST":
        # Collect health data from POST request
        heart_rate = float(request.POST.get("heart_rate", 70))
        sleep_hours = float(request.POST.get("sleep_hours", 8))
        steps = int(request.POST.get("steps", 10000))
        calories_burnt = float(request.POST.get("calories_burnt", 250))

        # Normal ranges
        heart_rate_normal = 77  # Normal range for heart rate (bpm)
        sleep_normal = 9  # Normal range for sleep hours
        steps_normal = 10000  # Normal range for steps
        calories_burnt_normal = 3000  # Normal range for calories burnt

        # Generate graphs for each metric
        heart_rate_graph = generate_comparison_graph(heart_rate, "Heart Rate (bpm)", heart_rate_normal)
        sleep_graph = generate_comparison_graph(sleep_hours, "Sleep Hours (hours)", sleep_normal)
        steps_graph = generate_comparison_graph(steps, "Steps", steps_normal)
        calories_graph = generate_comparison_graph(calories_burnt, "Calories Burnt (kcal)", calories_burnt_normal)

        # Prepare health data for AI recommendation
        health_data = {
            "heart_rate": heart_rate,
            "sleep_hours": sleep_hours,
            "steps": steps,
            "calories_burnt": calories_burnt
        }

        # Get AI-generated recommendations
        ai_recommendation = get_gemini_ai_recommendation(health_data)

        # Return both graphs and AI response in the JSON response
        return JsonResponse({
            "heart_rate_graph": heart_rate_graph,
            "sleep_graph": sleep_graph,
            "steps_graph": steps_graph,
            "calories_graph": calories_graph,
            "recommendations": ai_recommendation
        })

    return render(request, "healthinsights.html")





