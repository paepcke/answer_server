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
        elif qID == 'otherQ':
            resHTML = 'Answer to otherQ: 42'
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
    
    def serveQuestionPage(self):
        with open(os.path.join(os.path.dirname(__file__), 'html/questionList.html')) as fd:
            page = ''.join(fd.readlines())
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(page)
        
    
    def sendHTMLResponse(self, resHTML):
        self.wfile.write("<html><head><title>Answer</title><style>body {background-color:#b0c4de; }</style></head>")
        self.wfile.write("<body><p>%s</p>" % resHTML)
        self.wfile.write("</body></html>")
        
    
if __name__ == '__main__':
    httpd = AnswerServer()
    print time.asctime(), "Server Starts - %s:%s" % (httpd.myHostname, httpd.listenOnPort)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print time.asctime(), "Server Stops - %s:%s" % (httpd.myHostname, httpd.listenOnPort)
    