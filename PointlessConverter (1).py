# import libraries
import psycopg2
import os
import datetime
from liblas import file
from cStringIO import StringIO
import webbrowser
from flask import flash

# define the binary function to get the material path of a leaf node in an octree
def getMaterialPath(depth, x, y, z):
	ocKey = ""
	for i in range(depth, 0, -1):
		digit = 0
		mask = 1 << (i-1)
		if (x & mask) != 0:
			digit += 1
		if (y & mask) != 0:
			digit += 2
		if (z & mask) != 0:
				digit += 4
		ocKey += str(digit)
	return ocKey


def LasToOctree(depth, lasFile):
	# Open .Las file
	f = file.File(lasFile, mode='r')
	h = f.header

	print "Calculate BBox translation and scaling"
	# check bounding to calculate scaling factor
	lenX = h.max[0] - h.min[0]   # length in x direction
	lenY = h.max[1] - h.min[1]   # length in y direction
	lenZ = h.max[2] - h.min[2]   # length in Z direction

	# Putting the BBox min coordinates at 0
	if (h.min[0] < 0):
		translateX = abs(h.min[0])
	elif (h.min[0] > 0): 
		translateX = 0 - h.min[0]
	else:
		translateX = 0

	if (h.min[1] < 0):
		translateY = abs(h.min[1])
	elif (h.min[1] > 0): 
		translateY = 0 - h.min[1]
	else:
		translateY = 0

	if (h.min[2] < 0):
		translateZ = abs(h.min[2])
	elif (h.min[0] > 0): 
		translateZ = 0 - h.min[2]
	else:
		translateZ = 0

	if (lenX != 2**depth) or (lenY != 2**depth) or (lenZ != 2**depth):
		# if scaling is required we take the maximum domain of the point cloud for scaling
		maxDomain = max([lenX, lenY, lenZ])
		scale = 2**depth / maxDomain
	else: 
		# if no scaling is required we set the scale to 1
		scale = 1

	# open a text file to write the points to and a text file to write the materialised paths to
	PointsWriter = open("temp.txt", "w")

	# Load and iterate through the points  
	i = 0
	stringPoints =  StringIO()

	print "Start writing points to octree file"
	for point in f:

		#scale point 
		x = (point.x + translateX) * scale
		y = (point.y + translateY) * scale       
		z = (point.z + translateZ) * scale

		# Snap point to leaf node by converting float to integer and truncate towards 0 
		LeafNode = (int(x),int(y),int(z))

		# retrieve Material path from box
		MaterialPath = getMaterialPath(depth, LeafNode[0], LeafNode[1], LeafNode[2])
 
		#retrieve point attributes

		stringPoints.write(str(i)+" "+str(MaterialPath)+" "+str(x)+" "+str(y)+" "+str(z))
		try: 
			stringPoints.write(" "+str((point.color.red >> 16) & 255)+" "+str((point.color.green >> 8) & 255)+" "+str((point.color.blue) & 255)+"\n")
		except:
			stringPoints.write(" 0 0 0\n")

		# store material points to file after every 100.000 records
		if i % 500 == 0:
			# print i
			PointsWriter.write(stringPoints.getvalue())
			#stringPoints.close()
			stringPoints =  StringIO()
		if (i % 100000 == 0) and (i > 0):
			print str(i)+ " points written"

		i += 1
		
	print str(i)+ " points written"

	# store the remaining points 
	PointsWriter.write(stringPoints.getvalue())
	stringPoints.close()

	# Close the writers
	PointsWriter.close()

	print "Done writing points to octree file"

def create_dbms(dbms_name, user, password):
	print "Create database"
	con = psycopg2.connect("host='localhost' user='"+ user + "' password='"+ password + "'")
	con.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
	cur = con.cursor()

	try:
		cur.execute('drop DATABASE ' + dbms_name)		
		print "Database already exists, replacing database"
	except:
		pass
	cur.execute('CREATE DATABASE ' + dbms_name)
	cur.close()
	con.close()

	conn = psycopg2.connect("host='localhost' dbname='"+dbms_name+"' user='"+ user + "' password='"+ password + "'")
	cur = conn.cursor()
	cur.execute('CREATE EXTENSION POSTGIS;')
	cur.execute('CREATE TABLE pointcloud(index varchar(100), materialpath varchar(100), x varchar(100), y varchar(100), z varchar(100), red varchar(3), green varchar(3), blue varchar(3));')
	cur.execute('CREATE TABLE emptyspace(materialpath varchar(100), x varchar(100), y varchar(100), z varchar(100), leafSize int);')
	conn.commit()


def write_dbms(dbms_name, table, user, password):
	print "Load octree file to database"

	conn = psycopg2.connect("host='localhost' dbname='"+dbms_name+"' user='"+ user + "' password='"+ password + "'")
	cur = conn.cursor()

	cur.execute("copy "+table+" FROM '"+ os.getcwd() + r"\temp.txt' delimiter ' ' csv;")

	conn.commit()

def call_dbms(dbms_name, user, password, threshold):
	# This function fetches the table pointcloud with full boxes from the database
	print "Retrieve full leaf nodes from database"

	conn = psycopg2.connect("host='localhost' dbname='"+dbms_name+"' user='"+ user + "' password='"+ password + "'")
	cur = conn.cursor()
	#this determines that a box has to include at least 2 points in order to be taken into consideration for the octree of empty space
	if treshold is '' or threshold is '1':
		cur.execute('SELECT materialpath FROM pointcloud;')
	else:
		cur.execute('SELECT materialpath FROM pointcloud GROUP BY materialpath HAVING (COUNT(index) >= '+ treshold +') LIMIT 100')
	table = cur.fetchall()

	return table

def find_empty(table, maximumLevels):
	# This function finds the empty nodes for every level in the tree
	print "Calculate the empty leaf nodes in the point cloud"

	tree = ['0', '1', '2', '3', '4', '5', '6', '7']
	empty = set()
	nonempty = [{str()}]

	# Iterates over the depth of the tree
	for level in range(maximumLevels):					

		# Stores all the nonempty nodes of the current tree level in a set, and adds the set to a list
		nonempty_cur_level = set()
		for entry in table:
			nonempty_cur_level.add(entry[0][0:level+1])
		nonempty.append(nonempty_cur_level)

		# Finds all the empty nodes in the current level of the tree, and stores these in a set
		for node in nonempty[level]:
			for number in tree:
				child = node + number
				if child not in nonempty[level+1]:
					empty.add(child)

	return empty	

def getCoord(depth, materialPath):
	#This function finds the coordinates of the empty space
    #checks the size of the voxel according to the lenght of the path
    if len(materialPath) < depth:
    	leafSize = (2 ** (depth - len(materialPath)))
    	# if (leafSize > 31):
    	# 	print leafSize
    else:
        leafSize = 1

    x = ''
    y = ''
    z = ''

    # check digit per digit
    for digit in range(len(materialPath)):
        # check which 0s/1s should be added to the binary coordinate strings  
        if int(materialPath[digit]) > 3:
            if int(materialPath[digit]) > 5:
                if int(materialPath[digit]) > 6:   #7
                    x +='1'
                    y +='1'
                    z +='1'
                else:           #6
                    x +='0'
                    y +='1'
                    z +='1'                   
            elif int(materialPath[digit]) > 4:     #5
                x +='1'
                y +='0'
                z +='1'
            else:               #4
                x +='0'
                y +='0'
                z +='1'
        elif int(materialPath[digit]) > 1:
            if int(materialPath[digit]) > 2:       #3
                x +='1'
                y +='1'
                z +='0'           
            else:               #2
                x +='0'
                y +='1'
                z +='0'
        else:
            if int(materialPath[digit]) > 0:       #1 
                x +='1'
                y +='0'
                z +='0'
            else:               #0
                x +='0'
                y +='0'
                z +='0'

    remainingLevels = "0"*(depth - len(materialPath))
    x += remainingLevels
    y += remainingLevels
    z += remainingLevels

    # convert the binary string to decimal integers
    x = int(x, 2)
    y = int(y, 2)
    z = int(z, 2)

    return str(materialPath)+" "+str(x)+" "+str(y)+" "+str(z)+" "+str(leafSize)

def emptyLeaf2DBMS(MaterialPaths, dbms_name, user, password, maximumLevels):
	print "Start writing empty leafs to database"
	i = 0
	stringEmpty = ""
	EmptyWriter = open("temp.txt", "w")

	for path in MaterialPaths:
		stringEmpty += getCoord(maximumLevels, path)+"\n"

       	# store empty leafs to file after every 100.000 records
		if i % 100 == 0:
			EmptyWriter.write(stringEmpty)
			stringEmpty = ""
		if (i % 100000 == 0) and (i > 0):
			print str(i)+ " empty leafs written"

		i += 1

	# store the remaining leafs
	EmptyWriter.write(stringEmpty)

	# Close the writers
	EmptyWriter.close()
	write_dbms(dbms_name, "emptyspace", user, password)
	print "Done writing empty leafs to database"

def CheckInput(lasFile, dbms_name, user, password, maximumLevels=8):
	error = False 
	# Check if the input filename is of type '.las'
	if lasFile.lower().endswith(('.las')):
		# Check if the file exists
		if (os.path.isfile(lasFile) == True ):
			# Test the database connection with user's username and password combination
			try: 
				con = psycopg2.connect("host='localhost' user='"+ user + "' password='"+ password + "'")
				con.close()
			except:
				# Raise error for wrong username/password combination
				print "Please provide the correct username and password combination for Postgres"
				flash("Please provide the correct username and password combination for Postgres")
				error = True
				return error, dbms_name

			
			# con.close()
		else:
			print lasFile + " does not exist"
			flash(lasFile + " does not exist")
			error = True
			return error, dbms_name
	else:
		# Raise error for wrong input file type
		print "The input file has to be of type '.las' " 
		flash("The input file has to be of type '.las' ")
		error = True
		return error, dbms_name

	if maximumLevels > 8:
		# The maximum number of octree levels that is allowed is 8  
		print "The octree level exceeds the allowed maximum level. Please set level to 8 or lower"
		flash("The octree level exceeds the allowed maximum level. Please set level to 8 or lower")
		error = True
		return error, dbms_name
		maximumLevels = 8

	dbms_name = dbms_name.lower()
	return error, dbms_name

def createConfigPY(dbms_name, user, password):
	file = open(os.getcwd() +"/config.py", "w")
	file.write('SQLALCHEMY_DATABASE_URI = "postgresql://'+user+':'+password+'@localhost/'+dbms_name+'"\n')
	file.close()
	return


def openWebsite(URL):
	new = 0 # open in a the same tab
	webbrowser.open(URL,new=new)


def Pointless(lasFile, dbms_name,  maximumLevels=8, user="postgres", password=""):
	# This is the master file calling all the other functions based on the user's input

	error, dbms_name = CheckInput(lasFile, dbms_name, user, password, maximumLevels)

	if error == False:
		print "Start loading "+lasFile+" file: " + str(datetime.datetime.now())
	else:
		return 


	# Call the different functions with the user's input values
	LasToOctree(maximumLevels, lasFile)
	create_dbms(dbms_name, user, password) 
	write_dbms(dbms_name, "pointcloud", user, password)
	
	EmptyMaterialPaths = find_empty(call_dbms(dbms_name, user, password), maximumLevels)
	emptyLeaf2DBMS(EmptyMaterialPaths, dbms_name, user, password, maximumLevels)

	print "Finished writing '"+lasFile+"' to octree database '"+dbms_name+"': " + str(datetime.datetime.now())
	flash("Finished writing '"+lasFile+"' to octree database '"+dbms_name+"': " + str(datetime.datetime.now()))

	createConfigPY(dbms_name, user, password)
	# openWebsite("http://pointless.bitballoon.com/")



if (__name__ == "__main__"):
	
	Pointless('bouwpub9.las', "test", 8)

	# inputSet = [('11',),('20',),('30',)]
	# EmptyMaterialPaths = find_empty(inputSet, 2)
	# emptyLeaf2DBMS(EmptyMaterialPaths, "test","postgres", "", 2)


	