import sys
import socket
import select
#from time import time
import time
import json
import random

input_ports = []
outputs = {}
config_router_id = []
#periodic_update_timer = 30 in RIP specification but for developing and testing using a smaller number
periodic_update_timer = 6
#garbage_collection_timer = 30 #30 in RIP specification but for developing and testing using a smaller number
garbage_collection_timer = 30
localhost = "127.0.0.1"
timeout = 5
garbage_timeout = 5

def parse_configuration_file():
    
    check_config_file_input_ports = []
    check_config_file_output_ports = []
    
    try:
        file_name = sys.argv[1]
        if len(sys.argv) != 2:
            print("Please provide one configuration file as a paramater")
            exit()            
    except IndexError:
        print("Please provide one configuration file as a paramater")
        exit()
        
    with open(file_name, 'r') as config:
        for line in config:
            if line.startswith('router-id,'):
                try:
                    given_router_id = int(line.strip("\n").split(",")[1].strip(" "))
                    if given_router_id not in range(1, 64001):
                        print("Router id must be between 1 and 64000 (inclusive)")
                        exit()
                    else:
                        config_router_id.append(given_router_id)
                except ValueError:
                    print("Router id must be between 1 and 64000 (inclusive)")
                    exit()
            elif line.startswith('input-ports,'):
                check_config_file_input_ports = line.strip("\n").split(", ")[1:]
            elif line.startswith('outputs,'):
                check_config_file_output_ports = line.strip("\n").split(", ")[1:]
            elif line == "\n":
                continue
            elif line.startswith('#'):
                continue
            elif line.startswith('timer'):
                try:
                    given_timer_value = int(line.strip("\n").split(", ")[1:][0])
                    if given_timer_value < 0:
                        print("Please provide a valid timer value")
                        exit()
                    else:
                        periodic_update_timer = timer
                except ValueError:
                    print("Please provide a valid timer value")
                    exit()
            else:
                print("The configuration file is not in the correct format")
                exit()
                
    #If there is no router id given print an error message and exit the program as this is a required parameter
    if len(config_router_id) == 0:
        print("You are missing one or more mandatory parameters: router-id, input-ports or outputs")
        exit()        
            
    #check the input numbers are correct, if so, append to the input_ports list
    for port in check_config_file_input_ports:
        try:
            int_port = int(port)
            if int_port not in range(1024, 64001):
                print("Port numbers must be between 1024 and 64000 (inclusive)")
                exit()
            else:
                if int_port in input_ports:
                    print("A port number can be used at most once")
                    exit()
                else:
                    input_ports.append(int_port)
        except ValueError:
            print("Port numbers must be between 1024 and 64000 (inclusive)")
            exit()
    
    #If there are no inputs given print an error message and exit the program as this is a required parameter
    if len(input_ports) == 0:
        print("You are missing one or more mandatory parameters: router-id, input-ports or outputs")
        exit()
    
    #check the outputs numbers are correct, if so, add to the outputs dictionary with key value being {output_port: [metric, neighbored_router_id]}
    for output in check_config_file_output_ports:
        output_split = output.split("-")
        if len(output_split) != 3:
            print("Please specify the outport port number, metric and neighbored router id in this format: port,metric,neighbored router id")
            exit()            
        input_port_peer_router, peer_instance_link_value, peer_router_id = output_split
        try:
            output_port = int(input_port_peer_router)
            metric_to_neighbored_router = int(peer_instance_link_value)
            int_peer_router_id = int(peer_router_id)
            if output_port not in range(1024, 64001):
                print("Port numbers must be between 1024 and 64000 (inclusive)")
                exit()
            else:
                if output_port in outputs or output_port in input_ports:
                    print("A port number can be used at most once")
                    exit()
                else:
                    outputs[output_port] = (metric_to_neighbored_router, int_peer_router_id)
        except ValueError:
            print("Port numbers must be between 1024 and 64000 (inclusive)")
            exit()
    
    #If there are no outputs given print an error message and exit the program as this is a required parameter
    if len(outputs) == 0:
        print("You are missing one or more mandatory parameters: router-id, input-ports or outputs")
        exit()
        
    #print("input-ports: " + str(input_ports))
    #print("outputs: " + str(outputs))
    #print("router_id " + str(config_router_id))    

#--------------------------------------------------------------------------------------------------------------------------------------

class Router:
    def __init__(self, router_id):
        self.router_id = router_id
        self.routing_table = {}
        self.output_sending_port = None
        self.UDP_input_port_sockets = self.create_UDP_sockets()
    
    def print_routing_table(self):
        displayed_table = "+" + ("-" * 40) + "+" + "\n"
        #displayed_table += ("|" + "   " + "routerID" + "     " + "Destination" + "   " + "  Cost" + " " + "   |" + "\n")
        displayed_table += ("|" + " " * 3 + "routerID" + ": {}".format(self.router_id) + " " * 26 + "|" + "\n")  
        displayed_table += "|" + " " * 3 + "DestinationID" + " " * 3 + "Cost" + " " * 3 + "Next hop" + " " * 6 + "|" + "\n"
        #displayed_table += "|" + "-" * 40 + "|" + "\n"
        if self.routing_table != {}:
            for neighbor, info in self.routing_table.items():
                cost = info[0]
                if len(info) == 5:
                    next_hop = info[-1]
                    displayed_table += ("|" + (" " * 3) + "{}".format(neighbor) + (" " * 15) + "{}".format(cost) + (" " * 6) + "{}".format(next_hop) + (" " * 13) + "|" + "\n")        
                else:                    
                    displayed_table += ("|" + (" " * 3) + "{}".format(neighbor) + (" " * 15) + "{}".format(cost) + (" " * 6) + (" " * 11) + "|" + "\n")  
                #displayed_table += ("|" + (" " * 6) + "{}".format(self.router_id) + (" " * 12) + "{}".format(neighbor) + (" " * 14) + "{}".format(metric) + (" " * 5) + "|" + "\n")
        else:
            displayed_table += ("|" + (" " * 40) + "|" +"\n")
        displayed_table += ("|" + (" " * 40) + "|" + "\n")
        displayed_table += ("|" + (" " * 40) + "|" + "\n")
        displayed_table += ("+" + ("-" * 40) + "+")
        return displayed_table
    
    def create_UDP_sockets(self):
        UDP_input_port_sockets = []
        
        for input_port in input_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #UDP
                sock.bind((localhost, input_port))
                UDP_input_port_sockets.append(sock)
            except:
                print("Unable to create or bind socket...")
                sock.close()
        self.output_sending_port = UDP_input_port_sockets[0] #Port that does all the sending (can only have one), can also recieve (done in for loop), all inputs receive but only one can send)
        return UDP_input_port_sockets
    
    def create_response_packet(self, metric):
        command_field = (2).to_bytes(1, byteorder="big")
        version_field = (2).to_bytes(1, byteorder="big")
        must_be_zero_field_one = (0).to_bytes(2, byteorder="big")
        address_family_identifier = (socket.AF_INET).to_bytes(2, byteorder="big")
        must_be_zero_field_two = (0).to_bytes(2, byteorder="big")
        address_field = (self.router_id).to_bytes(4, byteorder="big") #send own router id to neighbors
        must_be_zero_field_three = (0).to_bytes(4, byteorder="big")
        must_be_zero_field_four = (0).to_bytes(4, byteorder="big")
        metric_field = (metric).to_bytes(4, byteorder="big")
        response_packet = bytearray(command_field + version_field + must_be_zero_field_one + address_family_identifier + must_be_zero_field_two + address_field +
                                    must_be_zero_field_three + must_be_zero_field_four + metric_field)
        return response_packet
    
    def send_packet(self, neighbor_port, packet_to_send):
        """output_sending_port is the port which this router sends to neighbor,
        neighbor_port is which the neighbor receives from"""
        self.output_sending_port.sendto(packet_to_send, (localhost, neighbor_port))
        
    
    def check_received_packet(self, packet_received):
        valid_packet = True
        command_field = packet_received[0:1]
        version_field = packet_received[1:2]
        must_be_zero_field_one = packet_received[2:4]
        address_family_identifier = packet_received[4:6]
        must_be_zero_field_two = packet_received[6:8]
        address_field = packet_received[8:12] #router id of the neighbor who sent the packet
        must_be_zero_field_three = packet_received[12:16]
        must_be_zero_field_four = packet_received[16:20]
        metric_field = packet_received[20:24] 
    
        if int.from_bytes(command_field, "big") != 2:
            print("command_field is not equal to the right value packet dropped.")
            valid_packet = False
        
        if int.from_bytes(version_field, "big") != 2:
            print("version_field is not equal to the right value, packet dropped.")
            valid_packet = False
            
        if int.from_bytes(must_be_zero_field_one, "big") != 0:
            print("must_be_zero_field_one is not equal to the right value packet, dropped.")
            valid_packet = False
        
        #if int.from_bytes(address_family_identifier, "big") != 0:
            #print("")
            #valid_packet = False    
        
        if int.from_bytes(must_be_zero_field_two, "big") != 0:
            print("must_be_zero_field_two is not equal to the right value, packet dropped.")
            valid_packet = False    
            
        if int.from_bytes(must_be_zero_field_three, "big") != 0:
            print("must_be_zero_field_three is not equal to the right value, packet dropped.")
            valid_packet = False    
            
        if int.from_bytes(must_be_zero_field_four, "big") != 0:
            print("must_be_zero_field_four is not equal to the right value, packet dropped.")
            valid_packet = False        
            
        if int.from_bytes(metric_field, "big") > 15 or int.from_bytes(metric_field, "big") < 1:
            print("Metric out of range")
            valid_packet = False    
            
        return valid_packet
    
    def update_routing_table(self, packet_received):
        received_metric = int.from_bytes(packet_received[20:24], "big") 
        received_router_id = int.from_bytes(packet_received[8:12], "big")
        
        if received_router_id not in self.routing_table:
            self.routing_table[received_router_id] = [received_metric, False, 0, 0] # metric, flag, timeout, garbage timeout
            
        else:
            if received_metric < self.routing_table[received_router_id][0]:
                self.routing_table[received_router_id][0] = received_metric
     
    def create_routing_table(self, destRouterId, metric):
        packet_id = (3).to_bytes(4, byteorder="big")
        source_dest = (self.router_id).to_bytes(4, byteorder="big") #send own router id to neighbors
        metric_field = (metric).to_bytes(4, byteorder="big")
        destRouterId = (destRouterId).to_bytes(4, byteorder="big") #send own router id to neighbors
        
        return bytearray(packet_id + source_dest + metric_field + destRouterId)
    
    def update_table_other_packet(self, response_packet):
        source_dest = int.from_bytes(response_packet[4:8], "big")
        cost = int.from_bytes(response_packet[8:12], "big")        
        dest_router_id = int.from_bytes(response_packet[12:16], "big")
        
        print(self.routing_table)
        
        if dest_router_id not in self.routing_table and dest_router_id != self.router_id:
            received_metric = self.routing_table[source_dest][0] + cost
            self.routing_table[dest_router_id] = [received_metric, False, 0, 0] # metric, flag, timeout, garbage timeout
            self.routing_table[dest_router_id].append(source_dest) # adds next hop router as the 5th element inside our list value
        
        if dest_router_id in self.routing_table and dest_router_id != self.router_id:
            received_metric = self.routing_table[source_dest][0] + cost
            current_cost = self.routing_table[dest_router_id][0]
            print("dest router id is ", dest_router_id)
            print("received metric is ", received_metric)
            print("current cost is ", current_cost)
            if received_metric < current_cost:
                self.routing_table[dest_router_id] = [received_metric, False, 0, 0]
                self.routing_table[dest_router_id].append(source_dest) # adds next hop router as the 5th element inside our list value
            

def main():   
    parse_configuration_file()
    router = Router(config_router_id[0])
    
    print(router.print_routing_table()) #routing table should still be empty at this stage (haven't received anything from neighbors)
    print("\n")
    print("dsaffdg")
    
    #Sockets created for all the input ports and output port created for the port that does all the sending to neighbors (only one)
    UDP_input_port_sockets = router.UDP_input_port_sockets
    
    while True:
        
        current_time = round(time.time())
        
        #if current_time % 6 == 0: #implement timer later #------------------------ implement periodic updates later ----------------------------------------
            #print(current_time)
        
        for output_port, value in outputs.items(): #create a packet and send off to this router's neighbors
            metric = value[0]
            create_packet = router.create_response_packet(metric)
            router.send_packet(output_port, create_packet)
        
        # receiving 
        readable, writable, exceptional = select.select(UDP_input_port_sockets, [], [], periodic_update_timer)
        print("readable is ", readable)
        for s in readable:
            print("sfdsg")
            received_bytes = s.recvfrom(1024)
            #print("I have recived stuff at router {}".format(router.router_id))
            #print("recieved bytes at router {} is {}".format(router.router_id, received_bytes))
            response_packet = received_bytes[0] # byte array
            #print("router_id: ", int.from_bytes(response_packet[8:12], "big"))
            print("response packet is ", response_packet)
            if int.from_bytes(response_packet[0:4], "big") != 3:
                if not router.check_received_packet(response_packet):
                    print("Packet is not valid, packet has been dropped")
                else:
                    router.update_routing_table(response_packet)
                print("sdfdsgf is ", int.from_bytes(response_packet[0:4], "big") != 3)
            else: 
                if len(router.routing_table) > 0:
                    router.update_table_other_packet(response_packet)
                    
        for output_port, value in outputs.items(): #create a packet and send off to this router's neighbors
            for destRouterID, value in router.routing_table.items():
                metric = value[0]                
                create_packet = router.create_routing_table(destRouterID, metric)            
                router.send_packet(output_port, create_packet) 
                
        
        
        
        
        print(router.print_routing_table())
        
        
if __name__ == "__main__":
    main()

#Test adding more than 15 routes (should be infinity)

