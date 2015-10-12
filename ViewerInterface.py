from flask import Flask, render_template, request, redirect, url_for, Response, flash, Markup, jsonify
from werkzeug import *
from werkzeug.datastructures import ImmutableMultiDict
from flask.ext.sqlalchemy import SQLAlchemy
from PointlessConverter import *

app = Flask(__name__)
app.config.from_pyfile("config.py")
db = SQLAlchemy(app)

@app.route('/')
def main():
 	return render_template('ViewerLogin.html')

@app.route('/viewer', methods=['POST'])
def viewData():
	dbms_name = request.form['InputDBMSname']
	user = request.form['InputUsername']
	password = request.form['InputPassword']

	if (user == "" and password == ""):
		createConfigPY(dbms_name=dbms_name, user="postgres", password="")
	elif (user == "" and password != ""):
		createConfigPY(dbms_name=dbms_name, user="postgres", password=password)
	elif (user != "" and password == ""):
		createConfigPY(dbms_name=dbms_name, user=user, password="")
	elif (user != "" and password != ""):
		createConfigPY(dbms_name=dbms_name, user=user, password=password)
	return render_template('Viewer.html')

@app.route('/_call_empty_db', methods=['POST'])
def call_empty_db():
    count = float(request.data[1:])
    if request.data[0] == 'x':
        sql = "select * from emptyspace as es where CAST(es.x AS float) >= {0} and CAST(es.x AS float) < {1};".format( str(count), str(count + 5))
    elif request.data[0] == 'y':
        sql = "select * from emptyspace as es where CAST(es.y AS float) >= {0} and CAST(es.y AS float) < {1};".format( str(count), str(count + 5))
    elif request.data[0] == 'z':
        sql = "select * from emptyspace as es where CAST(es.z AS float) >= {0} and CAST(es.z AS float) < {1};".format( str(count), str(count + 5))
    else:
        sql = "select * from emptyspace limit 10000;"
    # sql = 'select * from emptyspace;' CAST(coalesce(<column>, '0') AS integer)
    # print sql
    result = db.engine.execute(sql)
    emptyspace = []
    for row in result:
        emptyspace.append([int(row[1]),int(row[2]),int(row[3]),int(row[4])]) # for loading empty leaf nodes
    return jsonify(result=emptyspace)

@app.route('/_call_points_db', methods=['POST'])
def call_points_db():
    count = float(request.data[1:])
    if request.data[0] == 'x':
        sql = "select x, y, z from pointcloud as pc where CAST(pc.x AS float) >= {0} and CAST(pc.x AS float) < {1};".format(str(count), str(count + 5))
    elif request.data[0] == 'y':
        sql = "select x, y, z from pointcloud as pc where CAST(pc.y AS float) >= {0} and CAST(pc.y AS float) < {1};".format(str(count), str(count + 5))
    elif request.data[0] == 'z':
        sql = "select x, y, z from pointcloud as pc where CAST(pc.z AS float) >= {0} and CAST(pc.z AS float) < {1};".format(str(count), str(count + 5))
    else:
        sql = "select x, y, z from pointcloud limit 10000;"
    # sql = 'select x, y, z from pointcloud;'
    # print sql
    result = db.engine.execute(sql)
    points = []
    for row in result:
        points.append([float(row[0]),float(row[1]),float(row[2])]) # for loading point cloud
    return jsonify(result=points)





if __name__ == '__main__':
  	app.run(debug=True)