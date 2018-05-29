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
Sample of config of Redis is store.config, all parameters there are default and will be used if no config is provided


Script parameters:
    "-n", "--host" - hostname where the http server is run. Default is localhost
    "-p", "--port" - port of the http server. Default is 8080
    "-l", "--log"  - path to written log. Console output if used if no log is provided
    "-s", "--store_config" - path to redis config. If no config is provided will try to connect with default parameters
                             If connection is impossible or fails with several retries persistent storage won't be used
    