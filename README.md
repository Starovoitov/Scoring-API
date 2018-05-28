Example of using:

    python api.py -p 8080 -l /tmp/log.log
    
Example of running unittests:

    python -m unittest discover -p test.py
   
How to send one of handling http-requests*:

    curl -X POST -H "Content-Type: application/json" -d '{"account": "account", "login": "login", 
    "method": "clients_interests/online_score", "token": "55c...c95", "arguments": {arguments}' 
    http://127.0.0.1:8080/method/

*Samples of that could be taken from test.py

The api is a script for handling and validation incoming http requests of certain formats and 
collecting data from them in store (optionally). Using store is Redis database where records
are written in following format: 

    { account : {score: value, nclient1: [interests], nclient2: [interests]}}
    
If connection is failed for several attempt is failed then using of persistent storage is stopped
Cache for pulling data into db has 1000 bytes by default