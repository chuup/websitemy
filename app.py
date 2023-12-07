from flask import Flask, render_template, request, redirect, url_for, session,g ,send_file
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import pytz
import re
import random
from passlib.hash import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bson import ObjectId
from gridfs import GridFS
import io
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.secret_key = 'xyz'
connection_string = 'mongodb+srv://hackers_co:K9mDEAed8NYtQeLd@blog.xk7q6yw.mongodb.net/'
client = MongoClient(connection_string)
db = client["webdb"]  # Update with your MongoDB database name
users_collection = db["users"]
posts_collection = db["posts"]
comments_collection = db["comment"]
fs = GridFS(db)
########################################-------------------------------------------------
@app.route('/home')
def home():
    posts = list(posts_collection.find())  # Convert cursor to a list
    return render_template('home.html', posts=posts)

@app.route('/')
def index():
    if 'username' in session:
        try:
            # Fetch posts from MongoDB
            posts = list(posts_collection.find())  # Convert cursor to a list of posts

            # Fetch the user's details
            username = session['username']
            user_document = users_collection.find_one({'username': username})
            u = user_document['_id']

            # Retrieve the file from GridFS for each post (if available)
            for post in posts:
                file_id = post.get('file_id')
                if file_id:
                    file_data = fs.get(ObjectId(file_id))  # Convert file_id to ObjectId
                    post['file'] = file_data

            return render_template('index.html', username=username, user_document=user_document, u=u, posts=posts)
        
        except Exception as e:
            print("Error:", e)
            return "An error occurred while fetching posts."
    
    else:
        return redirect(url_for('home'))


# Create a new route to serve files
@app.route('/serve_file/<file_id>')
def serve_file(file_id):
    try:
        file_data = fs.get(ObjectId(file_id))

        # Get the filename from the file data
        filename = file_data.filename

        # Serve the file as an attachment with its original filename
        response = send_file(file_data, as_attachment=True, attachment_filename=filename)
        response.headers['Content-Type'] = file_data.content_type

        return response
    except Exception as e:
        print("Error:", e)
        return "File not found"

'''
#dashboard
@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        username = session['username']
        return render_template('dashboard.html', username=username)
    else:
        return redirect(url_for('login'))
'''


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username']
        password = request.form['password']

        # Check user credentials in MongoDB
        # user = users_collection.find_one({'email': username})
        # user = users_collection.find_one({'username': username}) #'password': password})
        user = users_collection.find_one({
            '$or': [
                {'username': username_or_email},
                {'email': username_or_email}
            ]
        })
        
        # print("User:", user)


        if user  and  bcrypt.verify(password, user['password']):
            # print("Login successful!")
            session['logged_in'] = True
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            # print("Invalid credentials.")
            return render_template('login.html', message='Invalid username or password. Please try again.')
    else:
        return render_template('login.html', message='')
    
########################################-------------------------------------------------
def extract_text_and_images(content):
    # Use a regular expression to find URLs in the content
    url_pattern = re.compile(r'https?://\S+')
    matches = url_pattern.finditer(content)

    parts = []
    last_end = 0

    for match in matches:
        start, end = match.span()

        # Add text before the match
        parts.append({'type': 'text', 'content': content[last_end:start]})

        # Add the image link
        parts.append({'type': 'image', 'content': match.group(0)})

        last_end = end

    # Add the remaining text after the last match
    parts.append({'type': 'text', 'content': content[last_end:]})

    return parts
########################################-------------------------------------------------
# Update the save_file_to_mongodb function to retain original file extension
def save_file_to_mongodb(file, db):
    fs = GridFS(db)
    filename = secure_filename(file.filename)  # Secure the filename to prevent path traversal
    file_id = fs.put(file, filename=filename)
    return file_id

# Update the add_post route to handle file upload and storage
@app.route('/add_post', methods=['GET', 'POST'])
def add_post():
    if request.method == 'POST':
        if 'username' in session:
            title = request.form['title']
            content = request.form['content']
            file = request.files['file']
            
            try:
                user = users_collection.find_one({'username': session['username']})
                user_id = user['_id']
                current_utc_time = datetime.utcnow()
                india_timezone = pytz.timezone('Asia/Kolkata')
                current_india_time = current_utc_time.replace(tzinfo=pytz.utc).astimezone(india_timezone)

                # Save the file to MongoDB using GridFS while retaining the original filename
                file_id = save_file_to_mongodb(file, db)

                # Modify the content to include the file_id or any other necessary details
                content = extract_text_and_images(content)

                # Insert the post into MongoDB along with the file_id
                posts_collection.insert_one({
                    'user_id': user_id,
                    'title': title,
                    'content': content,
                    'user': session['username'],
                    'date': current_india_time.strftime('%d %B %Y'),
                    'file_id': file_id  # Save the GridFS file_id in the database
                })

                return redirect(url_for('index'))
            except Exception as e:
                print("Error:", e)
                return "An error occurred while adding the post."
        else:
            return redirect(url_for('login'))
    return render_template('add_post.html')
########################################-------------------------------------------------
########################################-------------------------------------------------
def generate_otp():
    return str(random.randint(1000, 9999))
@app.route('/setting', methods=['GET', 'POST'])
def setting():
    if 'username' in session:
        if request.method == 'POST':
            new_username = request.form['new_username']
            new_password = request.form['new_password']
            new_password = bcrypt.hash(new_password)
            new_email = request.form['new_email']
            existing_us = users_collection.find_one({'username': new_username})
            existing_u = users_collection.find_one({'email':new_email})
        
            if existing_us:
                return render_template('profile.html', message='Username already taken. Please choose a different one.')
            if existing_u:
                return render_template('profile.html', message='Email already taken. Please choose a different one.')

            try:
                # Update username if it's not empty
                if new_username:
                    users_collection.update_one({'username': session['username']}, {'$set': {'username': new_username}})
                    session['username'] = new_username  # Update session with new username

                # Update password if it's not empty
                if new_password:
                    users_collection.update_one({'username': session['username']}, {'$set': {'password': new_password}})

                # Update email if it's not empty
                if new_email:
                    # if request.method != 'POST':
        # username = request.form['username']
                    email = new_email
                    otp = generate_otp()
                    print(otp)
                    if send_otp_email(email, otp):
                        session['email'] = email 
                        # session['username'] = username
                        # session['password'] = password
                        session['otp'] = otp
                        return render_template('verify_email.html')
                    else:
                        return 'Failed to send OTP. Please try again.'
                    # return redirect(url_for('update'))
                    # users_collection.update_one({'username': session['username']}, {'$set': {'email': new_email}})

                return redirect(url_for('profile'))  # Redirect to the profile page
            except Exception as e:
                print("Error:", e)
                return "An error occurred while updating profile."

        else:
            # Fetch user details for displaying on the profile page
            user_details = users_collection.find_one({'username': (session['username'])})
           
            return render_template('profile.html', user_details=user_details)
    else:
        return redirect(url_for('login'))
@app.route('/logout')
def logout():
    # Remove user session data
    session.pop('logged_in', None)
    session.pop('username', None)

    
    # Redirect to home page after logout
    return redirect(url_for('index'))
@app.route('/delete_post/<post_id>', methods=['POST'])
def delete_post(post_id):
    posts_collection.delete_one({'_id': ObjectId(post_id)})

    return redirect(url_for('index'))
@app.route('/redirect_page/<post_id>',methods=['GET', 'POST'])
def redirect_page(post_id):
    post_id = ObjectId(post_id)
    post = posts_collection.find_one({'_id': post_id})
    username=session.get('username')
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'like':
            if username:
                user_document = users_collection.find_one({'username': username})

                # Check if the user has liked the post already
                if user_document and 'liked_posts' in user_document:
                    if post_id in user_document['liked_posts']:
                        # User already liked the post, remove the like
                        posts_collection.update_one(
                            {'_id': post_id},
                            {'$inc': {'likes': -1}}
                        )
                        users_collection.update_one(
                            {'_id': user_document['_id']},
                            {'$pull': {'liked_posts': post_id}}
                        )
                    else:
                        # User has not liked the post, add the like
                        posts_collection.update_one(
                            {'_id': post_id},
                            {'$inc': {'likes': 1}}
                        )
                        users_collection.update_one(
                            {'_id': user_document['_id']},
                            {'$addToSet': {'liked_posts': post_id}}
                        )
                else:
                    # First time user is liking a post
                    posts_collection.update_one(
                        {'_id': post_id},
                        {'$inc': {'likes': 1}}
                    )
                    users_collection.update_one(
                        {'_id': user_document['_id']},
                        {'$addToSet': {'liked_posts': post_id}}
                    )
        # Redirect after form submission to prevent resubmission on page reload
        # return redirect(url_for('redirect_page', post_id=post['_id']))

        # Handle the comment submission
        comment_content = request.form.get('comment_content')
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)
        is_author=None
        if username:
            u = user_document
            u = users_collection.find_one({'username': username})
            # print(post['user'])
            is_author =  post['user'] == user_document['username']
        # Assuming you have a comments_collection for storing comments
        if comment_content:
            comments_collection.insert_one({
                'post_id': post_id,
                'user': session.get('username'),  # Assuming you have a user session
                'content': comment_content,
                'date': current_time,  # You may need to import datetime
                'Author':is_author
            })
            return redirect(url_for('redirect_page', post_id=post['_id']))
   #u = None
    print(session.get('username'))#'username'])
    # session['username']
    comments = comments_collection.find({'post_id': post_id})
    if username:
        user_document = users_collection.find_one({'username': username})
        if user_document is not None:
            u = user_document.get('_id')
            return render_template('dashboard.html', u=u, user_document=user_document, comments=comments, post=post)
        else:
            # Handle the case where user_document is None
            return render_template('dashboard.html', comments=comments, post=post)
    else:
        return render_template('dashboard.html', comments=comments, post=post)
    # post ={'_id': post_id}


from flask import jsonify

@app.route('/like_post/<post_id>', methods=['POST'])
def like_post(post_id):
    post_id = ObjectId(post_id)
    post = posts_collection.find_one({'_id': post_id})

    if post:
        # Increment the likes count for the post
        posts_collection.update_one(
            {'_id': post_id},
            {'$inc': {'likes': 1}}
        )

        return jsonify({'success': True, 'likes': post['likes'] + 1})

    return jsonify({'success': False, 'error': 'Post not found'}), 404

# ////////////////////////////////////
@app.route('/delete_comment/<comment_id>')
def delete_comment(comment_id):
    # Assuming you have a comments_collection for storing comments
    result = comments_collection.delete_one({'_id': ObjectId(comment_id)})
    # Redirect to the same page after deletion
    return redirect(request.referrer)
# ................
def send_otp_email(email, otp):
    sender_email = 'hackerscommunity434@gmail.com'  # Replace with your email address
    sender_password = 'rzoo xrxo eguk ywkf'  # Replace with your email password

    subject = 'Your OTP for verification from HC'
    body = f'Your OTP for verification is: {otp}'

    try:
        msg = MIMEMultipart()
        msg['From'] = 'HC <hackerscommunity434@gmail.com>'
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, msg.as_string())
        
        return True
    except Exception as e:
        print('Error while sending email:', e)
        return False

# Function to send OTP via email
# def send_otp_email(email, otp):
#     sender_email = 'hackerscommunity434@gmail.com'  # Replace with your email address
#     sender_password = 'axla hltg jwrn fygm'  # Replace with your email password

#     subject = 'Your OTP for verification'
#     body = f'Your OTP for verification is: {otp}'

#     try:
#         server = smtplib.SMTP('smtp.gmail.com', 587)  # Gmail SMTP server
#         server.starttls()
#         server.login(sender_email, sender_password)
#         server.sendmail(sender_email, email, f'Subject: {subject}\n\n{body}')
#         server.quit()
#         return True
#     except Exception as e:
#         print('Error while sending email:', e)
#         return False

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        existing_user = users_collection.find_one({'username': username})
        existing_use = users_collection.find_one({'email': email})
        
        if existing_user:
            return render_template('register.html', message='Username already taken. Please choose a different one.')
        if existing_use:
            return render_template('register.html', message='Email already taken. Please choose a different one.')
        
        # if 'otp' in session and 'email' in session:
        #     if session['email'] == email and session['otp'] == request.form['otp']:
        #         user_data = {
        #             "username": username,
        #             "email": email,
        #             "password": password
        #         }
        #         try:
        #             users_collection.insert_one(user_data)
        #             session.pop('otp', None)
        #             session.pop('email', None)
        #             return 'Registration successful!'
        #         except Exception as e:
        #             print('Error while inserting user:', e)
        #             return 'Failed to register. Please try again.'
        #     else:
        #         return 'Invalid OTP. Please try again.'
        
        otp = generate_otp()
        print(otp)
        if send_otp_email(email, otp):
            session['email'] = email 
            session['username'] = username
            session['password'] = password
            session['otp'] = otp
            return render_template('verify_otp.html')
        else:
            return 'Failed to send OTP. Please try again.'

    return render_template('register.html')

# ............................................../////////////
@app.route('/update', methods=['GET', 'POST'])
def update():
    if request.method != 'POST':
        # username = request.form['username']
        email = request.form['email']
        otp = generate_otp()
        print(otp)
        if send_otp_email(email, otp):
            session['email'] = email 
            # session['username'] = username
            # session['password'] = password
            session['otp'] = otp
            return render_template('verify_otp.html')
        else:
            return 'Failed to send OTP. Please try again.'
    return '. Please try again.'
@app.route('/verify_email', methods=['POST'])
def verify_email():
    if request.method == 'POST':
        new_email = session.get('email')
        users_collection.update_one({'username': session['username']}, {'$set': {'email': new_email}})
        return redirect(url_for('profile'))


        # .......................//////////////////////

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    if request.method == 'POST':
        email = session.get('email')
        user_otp = request.form['otp']
        usename=session.get('username')
        password=session.get('password')

        if 'otp' in session and 'email' in session:
            if session['email'] == email and session['otp'] == user_otp:
                hashed_password = bcrypt.hash(password)
                user_data = {
                    "username":usename ,  # You can uncomment this if needed
                    "email": email,
                    "password": hashed_password
                }
                try:
                    users_collection.insert_one(user_data)
                    session.pop('otp', None)
                    session.pop('email', None)
                    return redirect(url_for('login'))
                    # return 'Registration successful!' 
                except Exception as e:
                    print('Error while inserting user:', e)
                    return 'Failed to register. Please try again.'
            else:
                return 'Invalid OTP. Please try again.'

    # Redirect to registration page if accessed directly
    return render_template('register.html')

    # ......................FORGOT PASS
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        # Check if the email exists in the database
        user = users_collection.find_one({'email': email})

        if user:
            # Generate and send OTP
            otp = generate_otp()
            send_otp_email(email, otp)

            # Store OTP in the session for verification
            session['reset_email'] = email
            session['reset_otp'] = otp

            return redirect(url_for('verify_reset_otp'))
        else:
            return render_template('forgot_password.html', message='Invalid email. Please try again.')

    return render_template('forgot_password.html')
# verify...........
# ...

# Route for verifying OTP during password reset
@app.route('/verify_reset_otp', methods=['GET', 'POST'])
def verify_reset_otp():
    if request.method == 'POST':
        entered_otp = request.form['otp']

        # Check if entered OTP matches the stored OTP in the session
        if 'reset_otp' in session and session['reset_otp'] == entered_otp:
            # Redirect to password reset page
            return redirect(url_for('reset_password'))
        else:
            return render_template('verify_reset_otp.html', message='Invalid OTP. Please try again.')

    return render_template('verify_reset_otp.html')


# ...

# Route for resetting password
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        new_password = request.form['new_password']
        new_password = bcrypt.hash(new_password)


        # Update the user's password in the database
        if 'reset_email' in session:
            users_collection.update_one({'email': session['reset_email']}, {'$set': {'password': new_password}})

            # Clear the session variables
            session.pop('reset_email', None)
            session.pop('reset_otp', None)

            return redirect(url_for('login'))

    return render_template('reset_password.html')



    # /////////////////////

if __name__ == '__main__':
    # from waitress import serve
    # serve(app, host="0.0.0.0", port=8080)

    app.run(debug=True, port=5000)
