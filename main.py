import webapp2
import jinja2
import os
import urllib
import csv
from google.appengine.ext import ndb

#Sets up the Jinja environment, so we can pull in HTML code from a separate file
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


'''
The MainPage class will display the first page of HTML that the user sees.
  - Right now, it's just a form for them to upload a file with
'''
class MainPage(webapp2.RequestHandler):
	def get(self):
		#The HTML is kept in a separate file, to help keep the code organized
		template = JINJA_ENVIRONMENT.get_template('index.html')
		self.response.write(template.render())


'''
When the user selects a file to upload, they are sent to this page, which processes
the file, uploads the data to the database, and displays the output and any error messages for the user.
'''
class FileProcessing(webapp2.RequestHandler):
	#In case the location of the data changes, the index in the row where it's located can be easily changed here
	ITEM_PRICE_INDEX = 2
	ITEM_COUNT_INDEX = 3

	#After submitting the form to upload a file, a POST request is sent to this page, this is where that request goes
	def post(self):
		#The HTML for the page is stored in a separate file
		template_results = JINJA_ENVIRONMENT.get_template('results_page.html')
		self.response.write(template_results.render())

		#https://blog.whiteoctober.co.uk/2016/08/01/handling-uploads-with-app-engine-and-webapp2/
		#Grabbing the file from the POST request
		raw_file = self.request.POST.get('tsv_file')

		#Error checking to make sure the file is a tsv file
		try:
			if not raw_file.filename.endswith('.tsv'):
				self.response.write("Error. Uploaded file is not a tsv file!")
				return
		except:
			self.response.write("There was an error with the file")
			return

		#Once we have the file, I'm using python's csv module to read it as a tsv file
		try:
			csv_reader = csv.reader(raw_file.file, delimiter='\t')
		except:
			self.response.write("Error reading the tsv file!")
			return

		#If the user tries to upload a file that's already in the database, this method will remove the old data so it can be replaced with the new stuff 
		row_delete_count = self.delete_duplicate_data(raw_file)
		if row_delete_count > 0:
			self.response.write("{} Rows of data were removed.".format(row_delete_count))
			self.response.write("<br>")

		#Using a helper method to do the actual uploading of the new data to the database
		row_errors, total, row_count = self.upload_data(csv_reader, raw_file)

		#If upload_data returns None, then there was an error uploading the data, so we just return
		if row_errors is None:
			return

		#If there was an error uploading a row of data to the database, the upload_data method keeps a count of the number of errors, so we just
		#display that for the user
		if row_errors > 0:
			self.response.write("Removed {} rows from the file due to data errors.".format(row_errors))
			self.response.write("<br>")

		#Otherwise, just update the page to indicate how many rows of new data were added to the database
		self.response.write("<br>")
		self.response.write("Added {} rows of new data to the database.".format(row_count))
		self.response.write("<br>")
		self.response.write("<h4>Total Revenue: {}</h4>".format(total))
		self.response.write("<br>")

		#self.print_datastore()


	'''
	A helper method to upload the tsv file data to the database
	@param csv_reader - The tsv file, parsed by python's csv module
	@param raw_file - The file that was uploaded from the Main HTML page via a POST request
	'''
	def upload_data(self, csv_reader, raw_file):
		first_row = True
		total, row_count = 0, 0
		row_errors = 0
		file_key = None

		#This will extract the file name from the file data and create a record in the database for it
		file_key = File_Name(name=raw_file.filename)
		file_key.put()

		#The csv module should have converted each line of data in the tsv file into a list
		for row in csv_reader:
			#The first row of data in the file is a header file, so we just skip it
			if first_row == True:
				first_row = False
				continue

			#Otherwise, we take the price and count data and multiply it, and then put the row of data into the database
			#If there are any errors, the except block will catch them and display it for the user
			try:
				total += float(row[self.ITEM_PRICE_INDEX]) * float(row[self.ITEM_COUNT_INDEX])
				if file_key is not None and file_key.key is not None:
					row_key = Data_Row(item=row[0],description=row[1],price=row[2],count=row[3],vendor=row[4],vendor_address=row[5], parent=file_key.key)
					row_key.put()
					row_count += 1
				else:
					self.response.write("Error.  File key was none.")
					return None, None, None
			except Exception as e:
					row_errors += 1
					self.response.write("Error. Exception: {}".format(e))
					self.response.write("<br>")

		return row_errors, total, row_count


	'''
	This method will remove any data for a file that has the same name as the current one a user is trying to upload
	@param raw_file - The file that was uploaded from the Main HTML page via a POST request
	'''
	def delete_duplicate_data(self, raw_file):
		#First, query the database to see if there are any file names that are the same
		file_query = File_Name.query(File_Name.name == raw_file.filename)
		row_delete_count = 0

		#If we found some duplicates, this will first remove the child entries, then delete the root file name
		for f in file_query:
			self.response.write("Found the same file name in database... The old data will be overwitten!")
			self.response.write("<br>")

			#Query to find any rows of data that have this filename as its parent, then delete them
			tmp_data = Data_Row.query(ancestor=f.key).fetch()
			for t in tmp_data:
				t.key.delete()
				row_delete_count += 1
			f.key.delete()

		return row_delete_count


	'''
	A short method to print out whatever is in the database
	'''
	def print_datastore(self):
		file_query = File_Name.query()
		for f in file_query:
			self.response.write("file: {}".format(f))
			self.response.write("<br>")
			tmp_data = Data_Row.query(ancestor=f.key).fetch()
			for t in tmp_data:
				self.response.write("data: {}".format(t))
				self.response.write("<br>")


'''
This class is how the file information is structured and saved in the database
'''
class File_Name(ndb.Model):
    name = ndb.StringProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)

'''
This class is how each individual row of data is structured and saved in the database
'''
class Data_Row(ndb.Model):
    item = ndb.StringProperty()
    description = ndb.StringProperty()
    price = ndb.StringProperty()
    count = ndb.StringProperty()
    vendor = ndb.StringProperty()
    vendor_address = ndb.StringProperty()


app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/upload',FileProcessing),
], debug=True)

