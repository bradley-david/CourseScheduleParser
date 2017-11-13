#!/usr/bin/env python
import sys
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import json
import time # sleep so it doesn't look like ddos
import pandas as pd
from bs4 import BeautifulSoup

CATALOG_YEAR = 20182 # I have no idea how they get this number 
HTML_COLUMNS = ["Unique", "Days", "Hour", "Room", "Instructor", "Status"]

# append courses from the entire page and return updated dataframe
def append_courses(source, dataframe):
    soup = BeautifulSoup(source, "html5lib")
    for table in soup("table"):
        print table["class"]
        if not table["class"] == ["rwd-table", "results"]:
            continue
        current_header = None
        current_number = None
        current_dept = None
        current_course = None
        for row in table("tr"):
            if row.find("td") and "class" in row.find("td").attrs and row.find("td")["class"] == ["course_header"]:
                current_header = row.find("td").getText()
                # so nice of them to separate the department from the rest by 2 spaces
                s1 = current_header.split("  ")
                current_dept = s1[0]
                s2 = s1[1].split(" ")
                current_number = s2[0]
                current_course = " ".join(s2[1:])
                continue

            course = {"department": current_dept, 
                        "name": current_course,
                        "course_number": current_number}
            for column in row("td"):
                if column["data-th"] in HTML_COLUMNS:
                    if column["data-th"] == "Days":
                        course["Days"] = []
                        for span in column("span"):
                            course["Days"].append(span.getText())
                        course["Days"] = "|".join(course["Days"])
                    elif column["data-th"] == "Room":
                        course["Room"] = []
                        for span in column("span"):
                            course["Room"].append(span.getText())
                        course["Room"] = "|".join(course["Room"])
                    elif column["data-th"] == "Hour":
                        course["Hour"] = []
                        for span in column("span"):
                            course["Hour"].append(span.getText())
                        course["Hour"] = "|".join(course["Hour"])
                    else:
                        course[column["data-th"]] = column.getText()
            dataframe = dataframe.append(course, ignore_index=True)                
            print course                    
    return dataframe
    print table

def query_catalog():
    # this redirects us to the login page and takes us back to course schedule
    # after we have successfully authenticated
    with open("auth.json.cfg") as f:
        auth = json.load(f)
    # list of departments with courses I care about
    with open("departments.json") as f:
        departments = json.load(f)
    driver = webdriver.Chrome()
    driver.get("https://utdirect.utexas.edu/apps/registrar/course_schedule/20182/")
    username_field = driver.find_element_by_id("IDToken1")
    username_field.clear()
    username_field.send_keys(auth["username"])
    password_field = driver.find_element_by_id("IDToken2")
    password_field.clear()
    password_field.send_keys(auth["password"])
    password_field.send_keys(Keys.ENTER)

    levels = ["L", "U"]
    url_base = "https://utdirect.utexas.edu/apps/registrar/course_schedule/%s/results/?search_type_main=FIELD&fos_fl=%s&level=%s"
    df = pd.DataFrame()

    for department in departments:
        for level in levels:
            driver.get(url_base % (CATALOG_YEAR, department.replace(" ", "+"), level))
            df = append_courses(driver.page_source, df)
            time.sleep(3)    
            # deal with paginated results
            while True:
                try:
                    next_nav_link = driver.find_element_by_id("next_nav_link")
                    
                # for some reason it raises an exception instead of returning none if there is no such element
                except:
                    break
                driver.get(next_nav_link.get_attribute("href")) 
                df = append_courses(driver.page_source, df)
                time.sleep(3)
    print df
    df.to_csv("data_query.csv")
if __name__ == "__main__":
    query_catalog()    
