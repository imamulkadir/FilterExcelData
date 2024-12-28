import pandas as pd
from flask import Flask, render_template, request, flash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Make sure to set a secure secret key

# Function to process the CSV and return date counts
def process_file(file_path, client, year, month):
    # Try reading the CSV file with different encodings
    try:
        df = pd.read_csv(file_path, encoding='ISO-8859-1')  # Use a different encoding if necessary
    except UnicodeDecodeError:
        flash("Error reading the CSV file. Please check the file encoding.", "error")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        flash(f"Error reading the CSV file: {e}", "error")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Strip leading/trailing spaces from column names
    df.columns = df.columns.str.strip()

    # Find all columns that have date-like values
    date_columns = df.columns[df.apply(pd.to_datetime, errors='coerce').notna().any()]
    if len(date_columns) == 0:
        flash("No date-like columns found in the CSV file.", "error")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Flatten the dataframe to extract all the dates from date-like columns
    all_dates = pd.to_datetime(df[date_columns].stack(), errors='coerce').dropna()

    # Count the occurrences of each date
    date_counts = all_dates.value_counts().reset_index(name='Number of Filings')
    date_counts.columns = ['Date', 'Number of Filings']

    # Filter by year if specified
    if year != "All":
        date_counts['Date'] = pd.to_datetime(date_counts['Date'])
        date_counts = date_counts[date_counts['Date'].dt.year == int(year)]

    # Filter by month if specified
    if month != "All":
        month_number = pd.to_datetime(month, format='%B').month
        date_counts = date_counts[date_counts['Date'].dt.month == month_number]

    # Ensure that the dataframe is not empty
    if date_counts.empty:
        flash("No data available for the given filters.", "warning")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Get the top 10 filing days with the most filings
    top_days = date_counts.nlargest(10, 'Number of Filings')

    # Get the lowest 10 filing days with the fewest filings
    lowest_days = date_counts.nsmallest(10, 'Number of Filings')

    return date_counts, top_days, lowest_days

@app.route("/", methods=["GET", "POST"])
def index():
    # Default values
    date_counts, top_days, lowest_days = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    total_filings = 0  # Default value for total filings

    if request.method == "POST":
        # Retrieve form data
        file = request.files["file"]
        client = request.form.get("client")
        year = request.form.get("year")
        month = request.form.get("month")

        # Save the file temporarily to process it
        if file:
            file_path = f"uploads/{file.filename}"
            file.save(file_path)

            # Process the file
            date_counts, top_days, lowest_days = process_file(file_path, client, year, month)

            # Calculate total filings
            total_filings = date_counts['Number of Filings'].sum()

    # Render the template with the results
    return render_template(
        "index.html",
        total_filings=total_filings,  # Pass total filings to the template
        date_counts=date_counts.to_html(classes='table table-striped'),
        top_days=top_days.to_html(classes='table table-striped'),
        lowest_days=lowest_days.to_html(classes='table table-striped'),
        clients=["Barclays", "Other"],
        years=["All", "2020", "2021", "2022", "2023", "2024"],
        months=["All", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    )

if __name__ == "__main__":
    app.run(debug=True)
