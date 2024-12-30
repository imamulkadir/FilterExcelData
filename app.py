import os
import pandas as pd
from flask import Flask, render_template, request, flash
from datetime import datetime
import logging

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Make sure to set a secure secret key

# Error handler to catch all errors
@app.errorhandler(Exception)
def handle_error(error):
    # Log the full error for debugging purposes
    app.logger.error(f"An error occurred: {error}")

    # Return a user-friendly error message
    return render_template('error.html', error_message="Something went sideways. Let's blame it on the weather. Try again?"), 500


UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Function to process the CSV and return date counts
def process_files(file_paths, client, year, month):
    combined_date_counts = pd.DataFrame()

    for file_path in file_paths:
        try:
            # Read the CSV file
            df = pd.read_csv(file_path, encoding='ISO-8859-1')  # Use a different encoding if necessary
        except UnicodeDecodeError:
            flash(f"Error reading the file {os.path.basename(file_path)}. Please check the file encoding.", "error")
            continue
        except Exception as e:
            flash(f"Error reading the file {os.path.basename(file_path)}: {e}", "error")
            continue

        # Strip leading/trailing spaces from column names
        df.columns = df.columns.str.strip()

        # Find all columns that have date-like values
        date_columns = df.columns[df.apply(pd.to_datetime, errors='coerce').notna().any()]
        if len(date_columns) == 0:
            flash(f"No date-like columns found in {os.path.basename(file_path)}.", "error")
            continue

        # Flatten the dataframe to extract all the dates from date-like columns
        all_dates = pd.to_datetime(df[date_columns].stack(), errors='coerce').dropna()

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

    # Format the Date column to exclude time
    combined_date_counts['Date'] = combined_date_counts['Date'].dt.date

    # Get the top 10 filing days with the most filings
    top_days = combined_date_counts.nlargest(10, 'Total Filings')

    # Get the lowest 10 filing days with the fewest filings
    lowest_days = combined_date_counts.nsmallest(10, 'Total Filings')

    return combined_date_counts, top_days, lowest_days


@app.route("/", methods=["GET", "POST"])
def index():
    # Default values
    date_counts, top_days, lowest_days = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    total_filings = 0  # Default value for total filings
    selected_filters = {"client": "All", "year": "All", "month": "All"}  # Default filter values

    if request.method == "POST":
        # Retrieve form data
        files = request.files.getlist("files")  # Use getlist to allow multiple file selection
        client = request.form.get("client")
        year = request.form.get("year")
        month = request.form.get("month")
        
        # Store the selected filters
        selected_filters = {"client": client, "year": year, "month": month}

        # Save the files temporarily to process them
        file_paths = []
        for file in files:
            if file:
                file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(file_path)
                file_paths.append(file_path)

        # Filter files based on the selected client
        if client != "All":
            file_paths = [file_path for file_path in file_paths if os.path.basename(file_path).startswith(client)]

        if not file_paths:
            flash("No matching files found for the selected client.", "error")
        else:
            # Process the files
            date_counts, top_days, lowest_days = process_files(file_paths, client, year, month)

            # Calculate total filings
            total_filings = date_counts['Total Filings'].sum()

    # Render the template with the results
    return render_template(
        "index.html",
        total_filings=total_filings,  # Pass total filings to the template
        date_counts=date_counts.to_html(classes='table table-striped ', index=False), header=False if not date_counts.empty else "",
        top_days=top_days.to_html(classes='table table-striped ', index=False, header=False) if not top_days.empty else "",
        lowest_days=lowest_days.to_html(classes='table table-striped ', index=False, header=False) if not lowest_days.empty else "",
        clients=["All", "Barclays", "Bank of America Corp.", "Citi Group", "BofA", "Other"],
        years=["All", "2022", "2023", "2024", "2025", "2026"],
        months=["All", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        selected_filters=selected_filters  # Pass the selected filters to the template
    )


if __name__ == "__main__":
    app.run(debug=True)
