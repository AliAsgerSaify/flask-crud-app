import time

import flask
from flask import request, jsonify, Flask, render_template, flash, redirect, url_for, send_file, Response
import requests
import json
import sqlite3
import os
import pandas as pd
from datetime import datetime
import openpyxl
import io

database = "database.db"
table = "qdata"

conn = sqlite3.connect(database)
cursor = conn.cursor()
cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {table} (
        ITS INTEGER PRIMARY KEY,
        NAME TEXT NOT NULL,
        AGE INTEGER,
        GENDER TEXT,
        CONTACT TEXT,
        ZONE TEXT,
        SUBZONE TEXT
    );
""")

# cursor.execute(f"select * from {table};")
# rows = cursor.fetchall()
# if not rows:
#     cursor.execute(f"""
#         CREATE TABLE IF NOT EXISTS {table} (
#             ITS INTEGER PRIMARY KEY,
#             NAME TEXT NOT NULL,
#             CONTACT TEXT,
#             ZONE TEXT,
#             "SUB-ZONE" TEXT
#         );
#     """)

app = Flask(__name__)
app.secret_key="the_secret_key"

def get_db_connection():
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/", methods=['GET', 'POST'])
def index():
    return render_template("index.html")

@app.route("/submit", methods=['GET','POST'])
def submit():
    its_id = request.form["ITS"]
    name = request.form["name"].title()
    contact = request.form["contact"]
    age = request.form["age"]
    zone = request.form["zone"].title()
    subzone = request.form["sub-zone"].title()
    gender = request.form.get('gender').title()

    if not all([its_id, name,age, gender, contact, zone, subzone]):
        flash('You cannot submit a Blank Form')
        return redirect('/')


    if not its_id.isnumeric() or len(its_id) > 8:
        flash('ITS ID should be numeric and have a length of less than or equal to 8 characters.')
        # return redirect('/')

    elif not contact.isnumeric() or len(contact) < 7:
        flash('Contact should be numeric and more than 7 digits.')
        # return redirect('/')

    else:
        # Check if ITS ID already exists in the database
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE ITS = ?", (its_id,))
        exists = cursor.fetchone()[0] > 0
        conn.commit()

        if exists:
            flash('ITS ID already exists. Please use a different ID.')
            # return redirect('/')

        # Insert data into the database
        data = {
            "ITS": int(its_id),
            "NAME": name,
            "AGE" : age,
            "GENDER": gender,
            "CONTACT": contact,
            "ZONE": zone,
            "SUBZONE": subzone
        }
        columns = ', '.join(data.keys())
        values = ', '.join(['?'] * len(data))


        cursor.execute(f"""INSERT INTO {table} ({columns}) VALUES ({values})""", list(data.values()))
        conn.commit()


    return redirect('/')

@app.route('/view', endpoint="view")
def view():
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} order by ITS ASC")
    rows = cursor.fetchall()
    conn.commit()
    conn.close()
    return render_template('view.html', rows=rows)


@app.route('/export', methods=['GET'])
def export():
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} ORDER BY ITS ASC")
    rows = cursor.fetchall()
    conn.close()
    # Create a DataFrame from the fetched data
    df = pd.DataFrame(rows, columns=[column[0] for column in cursor.description])
    timenow = datetime.now().strftime('%d-%m-%Y_%H-%M')
    # export_dir = "./export"
    # if not os.path.exists(export_dir):
    #     os.makedirs(export_dir)
    excel_file = f"exported_data_{timenow}.xlsx"
    # Create a BytesIO object
    output = io.BytesIO()
    # Write the Excel file to the BytesIO object
    df.to_excel(output, index=False)
    # Seek the BytesIO object back to the beginning
    output.seek(0)


    # Send the file to the user
    return Response(
        output.read(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': f'attachment; filename={excel_file}'
        }
    )


@app.route('/modify', methods=['GET', 'POST'])
def modify():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get the current record index from the form
        current_index = request.args.get('index', 0, type=int)

        # Fetch all records
        cursor.execute(f'SELECT * FROM {table} ORDER BY ITS ASC')
        records = cursor.fetchall()

        if not records:
            flash('No records found.', 'error')
            return render_template('modify.html', record=None, current_index=0, total_records=0)

        # Ensure current_index is within bounds
        current_index = request.args.get('index', 0, type=int)
        if current_index < 0 or current_index >= len(records):
            current_index = 0  # Reset to the first record if out of bounds

        # Get the current record
        record = records[current_index]

        if request.method == 'POST':
            # Update record
            if 'update' in request.form:

                its_id = request.form["ITS"]
                name = request.form["name"].title()
                age = request.form["age"]
                contact = request.form["contact"]
                zone = request.form["zone"].title()
                subzone = request.form["subzone"].title()
                gender = request.form.get('gender').title()

                try:
                    # Update the record in the database
                    cursor.execute(f'UPDATE {table} SET NAME=?, GENDER=?, CONTACT=?, ZONE=?, SUBZONE=?, AGE=? WHERE ITS={its_id}',
                                   (name, gender, contact, zone, subzone, age))
                    # conn.commit()

                    # Check if any row was updated
                    if cursor.rowcount == 0:
                        flash(f"No record found with ITS ID: {its_id}. Update failed.", "warning")
                    else:
                        flash(f"Record updated successfully for ITS ID: {its_id} !!", "success")

                    return redirect(url_for('modify', index=current_index))

                except Exception as e:
                    flash(f"Unable to update record because: {str(e)}", "error")
                    return redirect(url_for('modify', index=current_index))


            # Delete record
            elif 'delete' in request.form:
                try:
                    its_id = request.form["ITS"]
                    cursor.execute(f'DELETE FROM {table} WHERE ITS = ?', (its_id,))
                    conn.commit()
                    flash("Record deleted successfully !!", "success")
                except Exception as e:
                    flash('Error deleting record: ' + str(e), 'error')

                return redirect(url_for('modify', index=max(0, current_index - 1)))

        return render_template('modify.html', record=record, current_index=current_index, total_records=len(records))

@app.route('/modify/<int:index>')
def modify_index(index):
    return redirect(url_for('modify', index=index))

@app.route('/csvdb')
def csvdb():
    return render_template('csvdb.html')

# Route to handle CSV file upload
@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400

    if file and file.filename.endswith('.csv'):
        # Save the uploaded file
        # Get the original filename
        # original_filename = file.filename
        #
        # # Create a unique filename using the current timestamp
        # timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # unique_filename = f"{os.path.splitext(original_filename)[0]}_{timestamp}.csv"
        #
        # file_path = os.path.join('uploads', unique_filename)
        # file.save(file_path)

        # Read the CSV file and insert data into the database
        # data = pd.read_csv(file_path, header=0)
        data = pd.read_csv(file, header=0)
        # print(data.columns)

        data.columns = data.columns.str.strip()
        insert_data_to_db(data)

        return redirect(url_for('csvdb'))  # Redirect back to the csvdb page
    return "Invalid file format", 400

def insert_data_to_db(data):
    try:
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        for index, row in data.iterrows():
            # Capitalize each word in the relevant columns
            print(row[0])
            its = row[0]
            name = row[1].title()  # Capitalize Name
            age = row[6]
            gender = row[2].title()  # Capitalize Gender
            contact = row[3]  # Assuming Contact doesn't need capitalization
            zone = row[4].title()  # Capitalize Zone
            sub_zone = row[5].title()  # Capitalize Sub Zone

            cursor.execute(f"INSERT INTO {table} (ITS, Name, Gender, Contact, Zone, Subzone, AGE) VALUES (?,?, ?, ?, ?, ?, ?)",
                           (its, name, gender, contact, zone, sub_zone, age))

        flash("Bulk Data Inserted Successfully !!", "success")
        conn.commit()
        conn.close()

    except Exception as e:
        flash("Error occured while uploading: " + str(e), "error")


@app.route('/deleteall', methods=['GET', 'POST'])
def delete_all():
    if request.method == 'POST':
        # Execute the delete operation
        delete_all_data()

        # return redirect(url_for('view'))  # Redirect to another page after deletion

    return render_template('deleteall.html')

def delete_all_data():
    try:
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table}")
        conn.commit()
        conn.close()
        flash("All Data Deleted Successfully !!", "success")

    except Exception as e:
        flash("Error occured while deleting: " + str(e), "error")

conn.commit()
conn.close()

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8080)