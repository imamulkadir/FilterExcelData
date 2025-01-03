import os
import pandas as pd
from flask import Flask, render_template, request, flash
from datetime import datetime
import logging
from flask import session, redirect, url_for
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Make sure to set a secure secret key

# Load environment variables from .env file
load_dotenv()

# Access credentials from environment variables
USERS = {
    os.getenv("USERNAME_IMAMUL"): os.getenv("PASSWORD_IMAMUL"),
    os.getenv("USERNAME_HABIB"): os.getenv("PASSWORD_HABIB"),
    os.getenv("USERNAME_USER2"): os.getenv("PASSWORD_USER2")
}

# Login page route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Validate credentials
        if username in USERS and USERS[username] == password:
            session["username"] = username  # Store the logged-in user in session
            return redirect(url_for("index"))  # Redirect to the main page
        else:
            flash("Invalid username or password. Please try again.", "error")

    return render_template("login.html")


# Logout route
@app.route("/logout")
def logout():
    session.pop("username", None)  # Remove the username from session
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# Protect routes (decorator for routes that require login)
def login_required(func):
    def wrapper(*args, **kwargs):
        if "username" not in session:
            flash("You need to log in first.", "error")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# Error handler to catch all errors
@app.errorhandler(Exception)
def handle_error(error):
    app.logger.error(f"An error occurred: {error}")
    return render_template('error.html', error_message="Something went sideways. Let's blame it on the weather. Try again?"), 500


UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Function to process the CSV and return date counts
def process_files(file_paths, client, year, month):
    combined_date_counts = pd.DataFrame()
    top_months = pd.DataFrame()

    for file_path in file_paths:
        try:
            # Read the CSV file
            df = pd.read_csv(file_path, encoding='ISO-8859-1')
        except UnicodeDecodeError:
            flash(f"Error reading the file {os.path.basename(file_path)}. Please check the file encoding.", "error")
            continue
        except Exception as e:
            flash(f"Error reading the file {os.path.basename(file_path)}: {e}", "error")
            continue

        # Strip leading/trailing spaces from column names
        df.columns = df.columns.str.strip()

        # Find all columns with date-like values
        date_columns = df.columns[df.apply(pd.to_datetime, errors='coerce').notna().any()]
        if len(date_columns) == 0:
            flash(f"No date-like columns found in {os.path.basename(file_path)}.", "error")
            continue

        # Flatten the dataframe to extract all the dates from date-like columns
        all_dates = pd.to_datetime(df[date_columns].stack(), errors='coerce').dropna()

        # Exclude dates outside a reasonable range (e.g., between 1900 and the current year)
        valid_date_range = (all_dates >= pd.Timestamp('2022-01-01')) & (all_dates <= pd.Timestamp.now())
        all_dates = all_dates[valid_date_range]

        if all_dates.empty:
            flash(f"No valid date entries found in {os.path.basename(file_path)}.", "error")
            continue

        # Count the occurrences of each date
        date_counts = all_dates.value_counts().reset_index(name='Total Filings')
        date_counts.columns = ['Date', 'Total Filings']

        # Format the Date column to include only the date part
        date_counts['Date'] = date_counts['Date'].dt.date

        # Filter by year if specified
        if year != "All":
            date_counts['Date'] = pd.to_datetime(date_counts['Date'])
            date_counts = date_counts[date_counts['Date'].dt.year == int(year)]

        # Filter by month if specified
        if month != "All":
            month_number = pd.to_datetime(month, format='%B').month
            date_counts = date_counts[date_counts['Date'].dt.month == month_number]

        combined_date_counts = pd.concat([combined_date_counts, date_counts])

    # Group by Date and sum the filings for all files
    if not combined_date_counts.empty:
        combined_date_counts = combined_date_counts.groupby('Date', as_index=False).sum()

    # Extract the month and year from the Date column
    combined_date_counts['Year'] = pd.to_datetime(combined_date_counts['Date']).dt.year
    combined_date_counts['Month'] = pd.to_datetime(combined_date_counts['Date']).dt.month_name()

    # Sort months by filing count within each year
    if year == "All":
        # When "All" years are selected, sort by filing count without combining months
        top_months = combined_date_counts.groupby(['Year', 'Month'], as_index=False)['Total Filings'].sum()
        top_months = top_months.sort_values(by=['Total Filings'], ascending=False).head(12)
    else:
        # When a specific year is selected, group by month and sort by filing count
        top_months = combined_date_counts.groupby(['Month'], as_index=False)['Total Filings'].sum()
        top_months = top_months.sort_values(by='Total Filings', ascending=False).head(12)

    # Get the top 10 filing days with the most filings
    top_days = combined_date_counts.nlargest(12, 'Total Filings')

    # Get the lowest 10 filing days with the fewest filings
    lowest_days = combined_date_counts.nsmallest(12, 'Total Filings')

    return combined_date_counts, top_days, lowest_days, top_months



@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    date_counts, top_days, lowest_days, top_months = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    total_filings = 0
    selected_filters = {"client": "All", "year": "All", "month": "All"}

    if request.method == "POST":
        files = request.files.getlist("files")
        client = request.form.get("client")
        year = request.form.get("year")
        month = request.form.get("month")
        selected_filters = {"client": client, "year": year, "month": month}

        file_paths = []
        for file in files:
            if file:
                file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(file_path)
                file_paths.append(file_path)

        if client != "All":
            file_paths = [file_path for file_path in file_paths if os.path.basename(file_path).startswith(client)]

        if not file_paths:
            flash("No matching files found for the selected client.", "error")
        else:
            date_counts, top_days, lowest_days, top_months = process_files(file_paths, client, year, month)
            total_filings = date_counts['Total Filings'].sum()

    return render_template(
        "index.html",
        total_filings=total_filings,
        date_counts=date_counts.to_html(classes='table table-striped', index=False) if not date_counts.empty else "",
        top_days=top_days[['Date', 'Total Filings']].to_html(classes='table table-striped', index=False, header=False) if not top_days.empty else "",
        lowest_days=lowest_days[['Date', 'Total Filings']].to_html(classes='table table-striped', index=False, header=False) if not lowest_days.empty else "",
        top_months=top_months.to_html(classes='table table-striped', index=False, header=False) if not top_months.empty else "",
        clients=["All", "Barclays", "Bank of America Corp.", "Citi Group", "BofA", "Other"],
        years=["All", "2022", "2023", "2024", "2025", "2026"],
        months=["All", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        selected_filters=selected_filters
    )


if __name__ == "__main__":
    app.run(debug=True)