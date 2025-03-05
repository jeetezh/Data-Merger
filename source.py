
from flask import Flask, render_template
from flask_socketio import SocketIO
import time
import threading
import socket
import re
import webbrowser
from threading import Timer
from datetime import datetime
app = Flask(__name__)
socketio = SocketIO(app)
counter=0
results={}
data_interval=0
# Global flag to manage process state
is_running = False
count_broken=0
is_running = False
threads = []
sock_server = None
data_from_computer = {} # Using a dictionary for up to 3 spacecraft
data_lock = threading.Lock()
host_port=None
# Global variables for parameters, break value, and total parameters
total_para = b'' # Will store the calculated total parameters
break_value = {} # List to store break values dynamically
spaces = b'\x20'*5 # Value spaces to be used in break value construction
num_parameters = {} # Holds the number of parameters for each spacecraft
value=b'\x02\xef\xbf\x82\xef\xbe\xbb19102024082026'
spacecraft_details = {}
n=0
combined_data=b''
def compute_total_para_and_break_value():
    global total_para, break_value, spaces,num_parameters
    # Calculate total parameters (sum of parameters for each spacecraft)
    v=str(sum(num_parameters.values())) # Sum the number of parameters for allspacecraft
    v=v.encode('utf-8')
    total_para = b'0000' + v 
    
    # Start constructing the break_value dynamically
    break_value.clear() # Clear the break_value list before appending new values
    
    # Loop over the spacecrafts and create break_value for each
    for i in range(1, len(num_parameters) + 1):
        if num_parameters[i-1] > 0: # If the spacecraft has parameters
            # For each spacecraft, append break values to the list
            break_value[i-1]=value+total_para+spaces + (f"BRK_S/C{i}".encode())*num_parameters[i-1] + b'\x03'
    

    #socketio.emit('status',{'data':f"Break Value: {break_value}"})
    #socketio.emit('status',{'data':f"Total Parameters: {total_para}"})
    
def receive_data(computer_ip, port, index):
    global data_from_computer
    print("recieve")
    sock = None
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((computer_ip, port))
        print()
        t6=datetime.now().strftime('%Y-%m-%d  %H::%M::%S')
        socketio.emit('status',{'data':f"{t6} Connected to {computer_ip} on port {port}"})
    except socket.error as e:
            print(f"Error connecting to {computer_ip}: {e}")
            socketio.emit('status',{'data':f"Error connecting to {computer_ip}: {e}"})
            return
    
    while is_running:
        try:
            data = sock.recv(16384)
            #print(data)
            if data:
                with data_lock:
                    data_from_computer[index]=data
                    #print(index)
                    #print(data_from_computer[index])
                    #socketio.emit('status',{'data':f"started data receiving from {computer_ip}"})
        except socket.error as e:
            print(f"Socket error while receiving from {computer_ip}: {e}")
            socketio.emit('status',{'data':f"Socket error while receiving from {computer_ip}: {e}"})
            break
       
   
def start_data_acquisition(num_spacecraft ,spacecraft_details, host_ip, host_port):
    global sock_server, threads, is_running,data_from_computer,n,data_interval
# Create socket for PC3 to listen for PC4
    n=num_spacecraft
    sock_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_address = (host_ip, host_port)
    t2=datetime.now().strftime('%Y-%m-%d  %H::%M::%S')
    
    print(f" {t2} Binding to {server_address} for TDACS app server to connect")
    socketio.emit('status',{'data':f" {t2} Binding to {server_address} for TDACS app server to connect"})
    
    sock_server.bind(server_address)
    print("here")
    sock_server.listen(10)
    print("Waiting for TDACS app server to connect...")
    socketio.emit('status',{'data':f" {t2} Waiting for TDACS app server to connect..."})
    connection, client_address = sock_server.accept()  # PC4 connection
    print(f"Connection established with TDACS app server at {client_address}")
    t3=datetime.now().strftime('%Y-%m-%d  %H::%M::%S')
    socketio.emit('status',{'data':f" {t3} Connection established with TDACS app server at {client_address}"})
    
   # Start receiving data from each spacecraft
    for i in range(1, num_spacecraft + 1):
        ip = spacecraft_details[f'pc{i}_ip']
        port = int(spacecraft_details[f'pc{i}_port'])
        thread = threading.Thread(target=receive_data, args=(ip, port, i-1))
        thread.start()
        
    #threads.start()
        
    
    while is_running:
        
        with data_lock:
    # Combine and export data to PC4
            combine_and_export_data(connection,sock_server, client_address,data_from_computer,num_spacecraft)
            #print("from start function:")
            #print(data_from_computer)
            
        time.sleep(data_interval)
    
    # Close the server socket
    connection.close()
    sock_server.close()    

def combine_and_export_data(connection,sock_server, client_address,data_from_computer1,num_spacecraft):
    global break_values,is_running,total_para,count_broken,counter,results

    print("In Combine and Export Data")
    try:
        results={}
         # Wait for incoming data
        for i in range(num_spacecraft):
            #Replace missing data with corresponding break value
            #print(data_from_computer)
            trail=data_from_computer[i]
            results[i]=trail
            if not results[i]:
                trail1=break_value[i]
                results[i]=trail1
        #print(results)
        if not all(results):
            print("here")
            # Adjust boundaries and clean data for each spacecraft
            
            for i in range(1, num_spacecraft):
                pattern = re.search(rb"\x20([+-]?\d|BRK_S/C\d+)", results[i])
                if pattern:
                    results[i] = results[i][pattern.start() + 1:]  # Trim leading part
            
            for i in range(num_spacecraft):
                array = bytearray(results[i])
                array = array.replace(b'\n', b'')
                results[i] = bytes(array)

            # Clean the end of each spacecraft's data
            for i in range(num_spacecraft-1):
                array = bytearray(results[i])
                array = array.replace(b'\x03', b'')
                results[i] = bytes(array)
            combined_data=b''
            for dummy in results.values():
                #print(dummy)
                if dummy:
                
                    combined_data=combined_data+dummy
            
            
            #comprint("In Combine and Export Data")bined_data = combined_data.replace(first, otal_para)
            array = bytearray(combined_data)
            a=str(num_parameters[1])
            a=a.encode()
            
            
            first=b'0000'+a
            print(first)
            array = array.replace(first, total_para)
            combined_data = bytes(array)
            
            #socketio.emit('status',{'data':f"Data recieved: 1: {len(data_from_computer[0])} 2:{len(data_from_computer[1])} sent: {len(combined_data)}"})
            #print(combined_data)

            # Write to file
            #with open('output18.txt', 'a') as f:
                #data_str = str(combined_data)
                #f.write(data_str + '\n\n')
            #print(f"Written to output18.txt: {data_str}")

            # Send data to the server (TDACS)
            message=combined_data
            #print(message)
            
            try:
                t4=datetime.now().strftime('%Y-%m-%d  %H::%M::%S')
                connection.sendall(message)
                counter=counter+1
               
                for j in range(num_spacecraft):
                    spacecraft="update"+str(j+1)
                    socketio.emit(spacecraft,{'data':len(data_from_computer[j])})
                    
                socketio.emit('update5',{'data':counter})
                #socketio.emit('update',{'data':f" {t4} Data recieved: 1: {len(data_from_computer[0])}   2:{len(data_from_computer[1])}   3:{len(data_from_computer[2])}    Data sent: counter :{counter}  {len(combined_data)} "})
                print("Sent combined data to server")
                #socketio.emit('status',{'data':"Sent combined data to server"})
                socketio.emit('update6',{'data':len(combined_data)})
                
            except Exception as e:
                count_broken += 1
                print(f"Error sending data: {e}")
                socketio.emit('status',{'data':f"Error sending data: {e}"})
                socketio.emit('status',{'data':f"connection broked for {count_broken} times"})
                sock_server.listen(10)
                connection,client_address=sock_server.accept()
            # Clear the data
            for i in range(1,num_spacecraft+1):
                data_from_computer[i-1] = b''
                results[i-1]= b''
        #print(results)
    except Exception as e:
            
            print(f"{e},  {e.args}")
    finally:
        if connection:
            connection.close()
            print("Connection closed")
print("In Combine and Export Data")    
@app.route('/')
def index():
    return render_template('code_merge.html')


@socketio.on('start_process')
def start_process(data):
    global is_running ,spacecraft_details,num_parameters, count_broken,counter,num_spacecraft,data_interval
	
    if not is_running:
        is_running = True
        counter=0 
        count_broken=0 
        t1=datetime.now().strftime('%Y-%m-%d  %H::%M::%S')
        socketio.emit('status',{'data':f" {t1} process started"})
        
        num_spacecraft = int(data['num_spacecraft'])
        data_interval= int(data['data_interval'])
        for i in range(1, num_spacecraft + 1):
            spacecraft_details[f'pc{i}_ip'] = data[f'spacecraft{i}_ip']
            spacecraft_details[f'pc{i}_port'] = data[f'spacecraft{i}_port']
            # Fetch the number of parameters for each spacecraft and store in global dictionary
            num_parameters[i-1] = int(data[f'spacecraft{i}_parameters'])

        host_ip = data['host_ip']
        host_port = int(data['host_port'])
        #initial_num = int(data['initial_num'])
        #num_loops = int(data['num_loops'])
        socketio.emit('status',{'data':f" {t1} {host_ip}  {host_port}    {num_spacecraft}"})
        
        socketio.emit('status',{'data':f" {t1} process started"})
        #socketio.sleep(3)
        
        compute_total_para_and_break_value()
        threading.Thread(target=start_data_acquisition, args=(num_spacecraft, spacecraft_details, host_ip, host_port)).start()
    else:
        socketio.emit('status', {'data': "Process is already running."})
 
        
 
def open_browser():
    webbrowser.open_new('http://172.16.102.182:5000//')
    

@socketio.on('stop_process')
def stop_process():
    global is_running, count_broken,counter,n,data_from_computer,results,combined_data
    t5=datetime.now().strftime('%Y-%m-%d  %H::%M::%S')    
    for i in range(1,n+1):
        data_from_computer[i-1] = b''
        results[i-1]= b''
    
    
    counter=0 
    count_broken=0 
    combined_data=b''
    for j in range(n):
        spacecraft="update"+str(j+1)
        socketio.emit(spacecraft,{'data':len(data_from_computer[j])})
        
    socketio.emit('update5',{'data':counter})
    #socketio.emit('update',{'data':f" {t4} Data recieved: 1: {len(data_from_computer[0])}   2:{len(data_from_computer[1])}   3:{len(data_from_computer[2])}    Data sent: counter :{counter}  {len(combined_data)} "})
    print("Sent combined data to server")
    #socketio.emit('status',{'data':"Sent combined data to server"})
    socketio.emit('update6',{'data':len(combined_data)})
    if is_running:
        is_running = False
        socketio.emit('status', {'data': f" {t5} Process stopped.\n"})
       
    else:
        
        socketio.emit('status', {'data': "No process to stop."})


if __name__ == "__main__":
 

    # Delay opening the browser (1 second after starting the app)
    Timer(1, open_browser).start()
    
    # Run the Flask app using the local IP address
     socketio.run(app,host='172.16.102.182',port=5000,debug=False)