from flask import Flask, request, render_template, session, redirect, url_for, make_response
import MySQLdb, hashlib, os
import time
from decimal import *
from google.appengine.api import memcache

CLOUDSQL_PROJECT = 'asg89-1354'
CLOUDSQL_INSTANCE = 'asg89-mysql'

app = Flask(__name__)
app.secret_key = "1|D0N'T|W4NT|TH15|T0|3E|R4ND0M"

@app.route('/', methods=['POST','GET'])
def register():
	if 'username' in session:
		return render_template('index.html', username = session['username'])
		
	if request.method == 'POST':
		db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.226.148',user='root',passwd='root',db='instagram',port=3306)
		cursor = db.cursor()		
		
		username = request.form['username']
		password = request.form['password']
		type = request.form['type']
		if(username == '' or password == ''):
			return render_template('register.html')
			
		sql = "select username from users where username='"+username+"'"
		cursor.execute(sql)
		if cursor.rowcount == 1:
			return render_template('register.html')
		
		# Change the values below to change quota values: 1000 is approx 1MB
		if (type == '1'):
			quota = str(5000.0)
			files = str(10)
		else:
			quota = str(10000.0)
			files = str(15)
		
		sql = "insert into users (username, password, type, initial_quota, quota, files) values ('"+username+"','"+hashlib.md5(password).hexdigest()+"',"+type+","+quota+","+quota+","+files+")"
		
		cursor.execute(sql)
		db.commit()
		cursor.close()
		return render_template('login.html')
	else:
		return render_template('register.html')

		
@app.route('/login', methods=['POST','GET'])
def login():
	if 'username' in session:
		return render_template('index.html', username = session['username'])
		
	if request.method == 'POST':
		
		db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.226.148',user='root',passwd='root',db='instagram',port=3306)
		cursor = db.cursor()
		
		username = request.form['username']
		password = request.form['password']
		
		sql = "select username from users where username = '"+username+"' and password = '"+hashlib.md5(password).hexdigest()+"'"
		cursor.execute(sql)
		if cursor.rowcount == 1:
			results = cursor.fetchall()
			for row in results:
				session['username'] = username
				cursor.close()
				return render_template('index.html', username = session['username'])
		else:
			cursor.close()
			return render_template('login.html')
	else:
		return render_template('login.html')


@app.route('/logout', methods=['POST','GET'])
def logout():
	if 'username' in session:
		session.pop('username', None)
	return redirect(url_for('register'))


@app.route('/upload', methods=['POST','GET'])
def upload():
	if request.method == 'POST':
		total_time = time.clock()
		file = request.files['file']
		file_contents = file.read()
		hash = hashlib.md5(file_contents).hexdigest()
		
		db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.226.148',user='root',passwd='root',db='instagram',port=3306)
		cursor = db.cursor()
		
		sql = "select name from images where username = '"+session['username']+"' and hash = '"+hash+"'"
		cursor.execute(sql)
		if cursor.rowcount > 0:
			return render_template('index.html', username = session['username'])
		
		sql = "select quota, files from users where username = '"+session['username']+"'"
		cursor.execute(sql)
		results = cursor.fetchall()
		for row in results:
			quota = Decimal(row[0])
			files = int(row[1])
		
		quota -= Decimal(len(file_contents))/Decimal(1024.0)
		files -= 1
		print str(quota)
		print str(files)
		if(quota>=0.0 and files>=0):
			sql = "insert into images (username, hash, name) values ('"+session['username']+"','"+hash+"','"+file.filename+"')"
			cursor.execute(sql)
			key = session['username']+"_"+hash
			#memcache.set(key,file_contents)
			memcache.set(key,file_contents,time=7200)
			sql = "update users set quota = '"+str(quota)+"', files = '"+str(files)+"' where username = '"+session['username']+"'"
			cursor.execute(sql)
			db.commit()
		else:
			return 'Cannot upload the file as it will exceed the quota of files/size.'
		
		cursor.close()
		time_str = "The image was uploaded in "+str(round(Decimal(time.clock()-total_time),5))
		return time_str#redirect(url_for('list'))
	else:
		return render_template('index.html', username = session['username'])


@app.route('/list', methods=['POST','GET'])
def list():
	if 'username' not in session:
		return render_template('register.html')

	if request.method == 'GET':			
		total_time = time.clock()
		db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.226.148',user='root',passwd='root',db='instagram',port=3306)
		cursor = db.cursor()
		
		sql = "select hash, name from images where username = '"+session['username']+"'"
		cursor.execute(sql)
		results = cursor.fetchall()
		list = '<br><center><a href="login">Back</a></center><br>'
		list += '<table border="1"><col width="200"><col width="325"><col width="200"><col width="250"><th>Name</th><th>Image</th><th>Owner</th><th>Options</th>'
		for row in results:
			hash = row[0]
			name = row[1]
			key = session['username']+"_"+hash
			image = memcache.get(key)
			image = image.encode("base64")
			list += "<tr><td>"+name+"</td>"
			list += "<td><center><img src='data:image/jpeg;base64,"+image+"' height='200' width='200'/></center></td>"
			#list += "<td><center><img src='/static/images/Bing.jpg' height='75%' width='75%'/></center></td>"
			list += "<td><center>"+session['username']+"</center></td>"
			list += "<td><a href='view?id="+hash+"&u="+session['username']+"'>View</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
			list += "<a href='delete?id="+hash+"&u="+session['username']+"'>Delete</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
			list += "<a href='download?id="+hash+"&u="+session['username']+"'>Download</a></td></tr>"
		list += '</table>The image was viewed in:'+str(round(Decimal(time.clock()-total_time),5))
		cursor.close()
		return '''<html><head><title>Instagram</title><link rel="stylesheet" href="static/stylesheets/style.css"></head><body>'''+list+'''</body></html>'''
	else:
		return render_template('index.html', username = session['username'])
		
		
@app.route('/list_all', methods=['POST','GET'])
def list_all():
	if 'username' not in session:
		return render_template('register.html')
		
	if request.method == 'GET':			
		total_time = time.clock()
		db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.226.148',user='root',passwd='root',db='instagram',port=3306)
		cursor = db.cursor()
	
		sql = "select hash, name, username from images"
		cursor.execute(sql)
		results = cursor.fetchall()
		list = '<br><center><a href="login">Back</a></center><br>'
		list += '<table border="1"><col width="200"><col width="325"><col width="200"><col width="250"><th>Name</th><th>Image</th><th>Owner</th><th>Options</th>'
		for row in results:
			hash = row[0]
			name = row[1]
			username = row[2]
			key = username+"_"+hash
			image = memcache.get(key)
			image = image.encode("base64")
			list += "<tr><td>"+name+"</td>"
			list += "<td><center><img src='data:image/jpeg;base64,"+image+"' height='200' width='200'/></center></td>"
			list += "<td><center>"+username+"</center></td>"
			list += "<td><a href='view?id="+hash+"&u="+username+"'>View</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
			if username == session['username']:
				list += "<a href='delete?id="+hash+"&u="+username+"'>Delete</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
			list += "<a href='download?id="+hash+"&u="+username+"'>Download</a></td></tr>"
		list += '</table>The image was viewed in '+str(round(Decimal(time.clock()-total_time),5))
		cursor.close()
		return '''<html><head><title>Instagram</title><link rel="stylesheet" href="static/stylesheets/style.css"></head><body>'''+list+'''</body></html>'''
	else:
		return render_template('index.html', username = session['username'])
		

@app.route('/view', methods=['GET'])
def view():
	if request.method == 'GET':			
		total_time = time.clock()
		db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.226.148',user='root',passwd='root',db='instagram',port=3306)
		cursor = db.cursor()
		
		hash = request.args.get('id')
		username = request.args.get('u')
		
		sql = "select hash, name from images where username = '"+username+"' and hash = '"+hash+"'"
		cursor.execute(sql)
		results = cursor.fetchall()
		
		view = '<br><center><a href="list">Back</a></center><br>'
		view += '<table border="1"><col width="200"><col width="325"><th>Name</th><th>Image</th>'
		for row in results:
			hash = row[0]
			name = row[1]
			key = username+"_"+hash
			image = memcache.get(key)
			image = image.encode("base64")
			view += "<tr><td>"+name+"</td>"
			view += "<td><center><img src='data:image/jpeg;base64,"+image+"' height='200' width='200'/></center></td></tr>"
		view += '</table><br><hr><br>'
		
		view += "<div><form action='comment' method='post'><center>Comment on the image<br><br><textarea name='comment' rows='3' cols='50'></textarea><br><br><input type='hidden' name='username' value= '"+username+"'><input type='hidden' name='hash' value= '"+hash+"'><input type='submit' value='Comment'></center></form></div>"
		
		sql = "select username, comment from comments where owner = '"+username+"' and hash = '"+hash+"'"
		cursor.execute(sql)
		results = cursor.fetchall()
		
		view += '<table border="1"><col width="100"><col width="500"><th>Username</th><th>Comment</th>'
		for row in results:
			username = row[0]
			comment = row[1]
			
			view += "<tr><td>"+username+"</td>"
			view += "<td>"+comment+"</td></tr>"
		
		view += '</table>The image was uploaded in '+str(round(Decimal(time.clock()-total_time),5))
		cursor.close()
		return '''<html><head><title>Instagram</title><link rel="stylesheet" href="static/stylesheets/style.css"></head><body>'''+view+'''</body></html>'''
	else:
		return render_template('index.html', username = session['username'])


@app.route('/comment', methods=['POST','GET'])
def comment():
	if request.method == 'POST':
		
		db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.226.148',user='root',passwd='root',db='instagram',port=3306)
		cursor = db.cursor()
	
		owner = request.form['username']
		hash = request.form['hash']
		username = session['username']
		comment = request.form['comment']
		
		sql = "insert into comments (username, hash, owner, comment) values ('"+username+"','"+hash+"','"+owner+"','"+comment+"')"
		cursor.execute(sql)
		db.commit()
		cursor.close()
		return redirect(url_for('view', id = hash, u = owner))
		
@app.route('/download', methods=['GET'])
def download():
	if request.method == 'GET':			

		db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.226.148',user='root',passwd='root',db='instagram',port=3306)
		cursor = db.cursor()
		
		hash = request.args.get('id')
		username = request.args.get('u')
		
		sql = "select name from images where username = '"+username+"' and hash = '"+hash+"'"
		cursor.execute(sql)
		results = cursor.fetchall()
		for row in results:
			name = row[0]
			key = username+"_"+hash
			file_contents = memcache.get(key)
			
		response = make_response(file_contents)
		response.headers["Content-Disposition"] = "attachment; filename="+name
		
		cursor.close()
		return response
	else:
		return render_template('index.html', username = session['username'])
		
		
@app.route('/delete', methods=['GET'])
def delete():
	if request.method == 'GET':			
		total_time = time.clock()
		db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.226.148',user='root',passwd='root',db='instagram',port=3306)
		cursor = db.cursor()
		
		hash = request.args.get('id')
		username = request.args.get('u')
		
		sql = "delete from images where username = '"+username+"' and hash = '"+hash+"'"
		cursor.execute(sql)
		db.commit()
		
		key = username+"_"+hash
		memcache.delete(key)
		
		sql = "delete from comments where owner = '"+username+"' and hash = '"+hash+"'"
		cursor.execute(sql)
		db.commit()
		
		cursor.close()
		time_str = "The image was deleted in "+str(round(Decimal(time.clock()-total_time),5))
		return time_str#redirect(url_for('list'))
	
@app.errorhandler(404)
def page_not_found(e):
	"""Return a custom 404 error."""
	return 'Sorry, Nothing at this URL.', 404


@app.errorhandler(500)
def application_error(e):
	"""Return a custom 500 error."""
	return 'Sorry, unexpected error: {}'.format(e), 500