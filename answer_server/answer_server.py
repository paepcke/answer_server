#!/usr/bin/env python
'''
Created on Nov 11, 2013

@author: paepcke
'''

import BaseHTTPServer
import os
import socket
import time
import urlparse

import mysqldb


LISTEN_ON_PORT=8000

class AnswerServer(BaseHTTPServer.HTTPServer):
    '''
    Ex. URL: http://mono.stanford.edu:8000/question?qID=NumStudents&className=CS144
    '''
    
    HTTP_BAD_REQUEST = 400

    def __init__(self, mysqldHostname='localhost', mysqldPort=3306, listenOnPort=LISTEN_ON_PORT):
        #super(AnswerServer, self).__init__(('', listenOnPort), AnswerServerRequestHandler) 
        BaseHTTPServer.HTTPServer.__init__(self, ('', listenOnPort), AnswerServerRequestHandler) 
        self.mysqldHostname = mysqldHostname
        self.mysqldPort = mysqldPort
        self.listenOnPort = listenOnPort
        
        self.mysqldb = mysqldb.MySQLDB(user='paepcke')
        self.myHostname = socket.gethostname()
        
        self.edxCache = {}
        
class AnswerServerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    
    URL_ACTION_POS   = 2  # urlparse res position of 'question' in http://...:portnum/question?...
    URL_QUERY_POS    = 4
    
    # ------------------------------  Question Answering Methods ----------------------    
    
    # Each method in this section knows how to answer one question
    # that is offered by the questionList.html answer server service
    # page:
    
    def answerQNumStudents(self, qID, queryDict):
        '''
        Called from request handler when a query about number of
        students in a particular class is requested. We expect
        attr className to be the name of the class. If that
        is missing we write an HTTP error to client browser, 
        and return None.
        @param queryDict: dict including all attr/val mappings from the URL query part
        @type queryDict: {<String,String>}
        @return: returns None if error was detected and handled. Else returns
                 an HTML snippet that the caller will splice into a 200
                 response to the browser.
        '''
        try:
            className = queryDict['className']
            # HTML attr values come inside singleton arrays:
            if isinstance(className, list) and len(className) > 0:
                className = className[0]
            else:
                self.send_error(AnswerServer.HTTP_BAD_REQUEST, 'Class name is in wrong format: %s' % str(className))
        except KeyError:
            self.send_error(AnswerServer.HTTP_BAD_REQUEST, "The query did not include a class name.")
            return None
        
        # In cache? Get this question's cache entry if it exists:
        numStudentsCacheEntry = self.server.edxCache.get(qID, None)
        # If no cache entry exists for this question, create one:
        if numStudentsCacheEntry is None:
            self.server.edxCache[qID] = {}
        else:
            cachedRes = numStudentsCacheEntry.get(className, None)
            if cachedRes is not None:
                return 'Number of students in %s is %d' % (className, cachedRes)
        
        # Not in cache: do the query and update the cache:
        # The double-% is needed to make the %like% for MySQL:
        query = "SELECT COUNT(DISTINCT anon_screen_name) FROM Edx.EdxTrackEvent WHERE course_id LIKE '%%%s%%';" % className
        for res in self.server.mysqldb.query(query):
            # Results come as a tuple, like (349,):
            numStudents = res[0]
            # Cache for future:
            self.server.edxCache[qID][className] = numStudents 
            return 'Number of students in %s is %s' % (className, str(numStudents))  
        return 
            
    
    def answerSubmissionOfProbSolutions(self, qID, queryDict):
        '''
        Answers the question: Show all student names of a particular class, with the
        correctness and times at which they submitted a solution to a given problem.
        We expect the following keys in queryDict: 'problem_id', and 'csv'. The latter
        is from a checkbox.  
        @param queryDict: dict including all attr/val mappings from the URL query part
        @type queryDict: {<String,String>}
        @return: returns None if error was detected and handled. Else returns
                 an HTML snippet that the caller will splice into a 200
                 response to the browser.
        '''
        try:
            problemID = queryDict['problemID']
            # HTML attr values come inside singleton arrays:
            if isinstance(problemID, list) and len(problemID) > 0:
                problemID = problemID[0]
            else:
                self.send_error(AnswerServer.HTTP_BAD_REQUEST, 'Problem ID is in wrong format: %s' % str(problemID))
        except KeyError:
            self.send_error(AnswerServer.HTTP_BAD_REQUEST, "The query did not include a problem ID.")
            return None

        # Is the 'CSV' checkbox checked?
        try:
            queryDict['csv']
            renderCSV = True
        except KeyError:
            renderCSV = False

        # In cache? Get this question's cache entry if it exists:
        studentSubmissionDates = self.server.edxCache.get(qID, None)
        # If no cache entry exists for this question, create one:
        if studentSubmissionDates is None:
            self.server.edxCache[qID] = {}
        else:
            cachedRes = studentSubmissionDates.get(problemID, None)
            if cachedRes is not None:
                if renderCSV:
                    return 'Table student submissions to problem %s is<br> %s' % (problemID, self.renderCSVTable(cachedRes, 'AnonS,SubmissionTime,Correctness'))
                else:
                    return 'Table student submissions to problem %s is<br> %s' % (problemID, self.renderHTMLTable(cachedRes, 'AnonS,SubmissionTime,Correctness'))

        # Not in cache: do the query and update the cache:
        # The double-% is needed to make the %like% for MySQL:
   
        query = "SELECT anon_screen_name,time,correctness FROM Edx.EdxTrackEvent WHERE problem_id='%s';" %\
                problemID
 
        resTable = []
        for res in self.server.mysqldb.query(query):
            # Results come as tuples:
            # Cache for future:
            resTable.append(res)
        self.server.edxCache[qID][problemID] = resTable
        if len(resTable) == 0:
            return 'No submissions found for problem %s.' % problemID
        else:
            if renderCSV:
                return 'Submissions to problem %s:</br> %s' % (problemID, self.renderCSVTable(resTable, 'AnonS,SubmissionTime,Correctness'))
            else:
                return 'Submissions to problem %s:</br> %s' % (problemID, self.renderHTMLTable(resTable, 'AnonS,SubmissionTime,Correctness'))
        
    # ------------------------------  Internal Methods ----------------------    
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
    def do_GET(self):
        """Respond to a GET request."""
        
        parms = urlparse.urlparse(self.path)
        action = parms[AnswerServerRequestHandler.URL_ACTION_POS]

        if action == '/':
            self.serveQuestionPage()
            return
        if action == '/invalidateCache':
            self.server.edxCache = {}            
            self.sendHTTPOKNoContent()
            return
        
        if action != '/question':
            self.send_error(AnswerServer.HTTP_BAD_REQUEST, 'Server only answers questions.')
            return
        
        queryDict = urlparse.parse_qs(parms[AnswerServerRequestHandler.URL_QUERY_POS])
        try:
            qID = queryDict['qID']
            if isinstance(qID, list) and len(qID) > 0:
                qID = qID[0]
            else:
                self.send_error(AnswerServer.HTTP_BAD_REQUEST, 'URL cannot be parsed into a question.')
                return
        except KeyError:
            self.send_error(AnswerServer.HTTP_BAD_REQUEST, 'No question ID was included in the URL')
            return
        
        if qID == 'NumStudents':
            resHTML = self.answerQNumStudents(qID, queryDict)
        elif qID == 'studentProblemSetSubmissions':
            resHTML = self.answerSubmissionOfProbSolutions(qID, queryDict)
        else:
            self.send_error(AnswerServer.HTTP_BAD_REQUEST, 'Unknown question: %s' % qID)
            return
        # Question was answered, and HTML snippet is in resHTML. 
        # If resHTML is None, then the handler method already sent
        # an appropriate error response, and we're done
        if resHTML is None:
            return
        
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.sendHTMLResponse(resHTML)

    
    def serveQuestionPage(self):
        with open(os.path.join(os.path.dirname(__file__), 'html/questionList.html')) as fd:
            page = ''.join(fd.readlines())
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(page)
        
    def sendHTTPOKNoContent(self):
        '''
        Returns to user agent a response 204, which means that request
        has been serviced, but nothing needs to be returned. Used, for inctance,
        with /invalidateCache request
        '''
        self.send_response(204)
        
    
    def sendHTMLResponse(self, resHTML):
        self.wfile.write("<html><head><title>Answer</title><style>body {background-color:#b0c4de; }</style></head>")
        self.wfile.write("<body><p>%s</p>" % resHTML)
        self.wfile.write("</body></html>")
        
    def renderCSVTable(self, tableArr, headerLine=''):
        '''
        Given an array of tuples that each constitute a CSV row,
        return one HTML string that renders the table as CSV, which
        can be copy/pasted into other applications.  
        @param tableArr: Array of tuples that contain comma-separated Python data
        @type tableArr: [(<any>)]
        '''
        if len(tableArr) == 0:
            return ''
        if len(headerLine) > 0:
            res = headerLine + '</br>'
        else:
            res = ''
        for oneTuple in tableArr:
            for element in oneTuple:
                if element is None:
                    element = 'n/a'
                res += str(element) + ','
            # Replace the last comma w/ '</br>' for an HTML newline
            if res.endswith(','):
                res = res[:-1] + '</br>'
        return res

    def renderHTMLTable(self, tableArr, headerLine=''):
        if len(tableArr) == 0:
            return ''
        res = "<table>"
        # Write header:
        if len(headerLine) > 0:
            res += "<tr>"
            for colName in headerLine.split(','):
                res += '<th>' + colName + '</th>'
            res += '</tr>'
        # and the rest:
        for oneTuple in tableArr:
            res += '<tr>'
            for element in oneTuple:
                if element is None:
                    element = 'n/a'
                res += '<td>' + str(element) + '</td>'
            res += '</tr>'
        return res
    
if __name__ == '__main__':
    httpd = AnswerServer()
    print time.asctime(), "Server Starts - %s:%s" % (httpd.myHostname, httpd.listenOnPort)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print time.asctime(), "Server Stops - %s:%s" % (httpd.myHostname, httpd.listenOnPort)
    