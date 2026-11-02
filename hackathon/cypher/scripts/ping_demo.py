import time
from neo4j import GraphDatabase
URI="neo4j+s://demo.neo4jlabs.com"
for db in ["movies","recommendations","northwind","fincen","twitter","companies","neoflix","gameofthrones","stackoverflow2","twitch","buzzoverflow","network","bluesky","offshoreleaks","slack","grandstack"]:
    t=time.time()
    try:
        with GraphDatabase.driver(URI, auth=(db,db), connection_timeout=8) as d:
            r,_,_=d.execute_query("MATCH (n) RETURN count(n) AS c", database_=db, routing_="r")
            print(db, "OK", r[0]["c"], round(time.time()-t,2), flush=True)
    except Exception as e:
        print(db, "ERR", type(e).__name__, str(e)[:100], round(time.time()-t,2), flush=True)
