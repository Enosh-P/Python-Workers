# Venue Scraping Worker

This is a simple Python Worker, used for backend service for Only Couples website. This Python worker service scrapes venue websites and extracting structured data using LLM.


## How it works

When a user wants to add a venue to the wedding planner space, the user can just paste the link in the text box and start processing.

1. Next.js will start the process by creating a new record in the database table shared by Next.js and Python worker.
2. The Next.js will add the link to the database with the status = 'pending'. It will then send the HTTP POST to the Python Worker. (basically calling the FastAPI endpoint)
3. The FastAPI which is listening will get the POST and starts the work. 
4. Now FastAPI will parse the JSON, call the function to scrape and summerize with the use of LLM
5. It parses the values into the JSON Schema. Then sends this data back to the database table and changes status to 'redy'
6. Next.js polls the task status and displays the result. (has a timeout, to show failure)
7. Also has a stop flag (by setting `cancel_flag = TRUE` in the database table) incase user decides to abort the process


**Quick Health Check:**
```bash
python test_health.py
```

Since this is the only server-level backend system required, we use a seperate deployment for this. The website is hosted in a serverless platform.

This involves a server to run and perform task on the background. 

This was finalized by the Council of LLMs(discussed with LLMs to arrive here and made them debate among themself) as the good design for this particular use case which minimalizes the infra, cost, complexity and failure point. Basically Server only when necessary!

