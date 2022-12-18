from http.server import BaseHTTPRequestHandler, HTTPServer


class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write('Server Alive\n'.encode())
        return


print('Server listening on port 8000...')
httpd = HTTPServer(('', 8000), MyHandler)
httpd.serve_forever()
