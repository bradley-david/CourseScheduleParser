#!/usr/bin/env python
from __future__ import unicode_literals
import sys
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import json
import time  # sleep so it doesn't look like ddos
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import enum

CATALOG_YEAR = 20182  # I have no idea how they get this number
HTML_COLUMNS = ["Unique", "Days", "Hour", "Room", "Instructor", "Status"]


class Course:
    def __init__(self,
                 department,
                 name,
                 number):
        self.department = department
        self.name = name
        self.number = number
        self.full_name = str(self.department) + str(self.number)
        self.sections = []
        self.dependencies = []

    def __str__(self):
        return "Course(%s)" % self.full_name

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def factory(df_row):
        return Course(
            df_row["department"],
            df_row["name"],
            df_row["course_number"]
        )


class Section:
    def __init__(self,
                 unique,
                 days_str,
                 hour_str,
                 room_str,
                 instructor,
                 status,
                 course):
        self.unique = unique
        self.days_str = days_str
        self.hour_str = hour_str
        self.room_str = room_str
        self.instructor = instructor
        self.status = status
        self.course = course

        # create objects for the times
        # zipped = zip(self.days_str.split("|"), self.hour_str.split("|"), self.room_str.split("|"))

    def __str__(self):
        return "Section(%s: %s)" % (self.course.full_name, self.unique)

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def factory(df_row, course):
        print df_row
        return Section(df_row["Unique"],
                       df_row["Days"],
                       df_row["Hour"],
                       df_row["Room"],
                       df_row["Instructor"],
                       df_row["Status"],
                       course)


class Dependency:
    def __init__(self, dependencyType, courses, ):
        pass


class DependencyType(enum.Enum):
    PREREQ = 0
    COREQ = 1


class Status(enum.Enum):
    OPEN = 0
    WAITLIST = 1
    CLOSED = 2

    def __str__(self):
        for k,v in vars(self.__class__).items():
            if v == self.value:
                return k

class Day(enum.Enum):
    MONDAY = 0
    TUESDAY = 0
    WEDNESDAY = 0
    THURSDAY = 0
    FRIDAY = 0
    SATURDAY = 0
    SUNDAY = 0


class DayTime:
    def __init__(self, day, time):
        self.day = day
        self.time = time

# append courses from the entire page and return updated dataframe
def append_courses(source, dataframe, courses, sections):
    soup = BeautifulSoup(source, "html5lib")
    for table in soup("table"):
        print table["class"]
        if not table["class"] == ["rwd-table", "results"]:
            continue
        current_header = None
        current_number = None
        current_dept = None
        current_course_name = None
        for row in table("tr"):
            if row.find("td") and "class" in row.find("td").attrs and row.find("td")["class"] == ["course_header"]:
                current_header = row.find("td").getText()
                # so nice of them to separate the department from the rest by 2 spaces
                s1 = current_header.split("  ")
                current_dept = s1[0]
                s2 = s1[1].split(" ")
                current_number = s2[0]
                current_course_name = " ".join(s2[1:])
                continue

            section = {"department": current_dept,
                       "name": current_course_name,
                       "course_number": current_number}
            print section.values()
            if None in section.values():
                print "None!!!!!!!!"
                continue

            for column in row("td"):
                if column["data-th"] in HTML_COLUMNS:
                    if column["data-th"] == "Days":
                        section["Days"] = []
                        for span in column("span"):
                            section["Days"].append(span.getText())
                        section["Days"] = "|".join(section["Days"])
                    elif column["data-th"] == "Room":
                        section["Room"] = []
                        for span in column("span"):
                            section["Room"].append(span.getText())
                        section["Room"] = "|".join(section["Room"])
                    elif column["data-th"] == "Hour":
                        section["Hour"] = []
                        for span in column("span"):
                            section["Hour"].append(span.getText())
                        section["Hour"] = "|".join(section["Hour"])
                    elif column["data-th"] == "Status":
                        text = column.getText()
                        if "open" in text.lower():
                            section["Status"] = Status.OPEN
                        elif "waitlist" in text.lower():
                            section["Status"] = Status.WAITLIST
                        else:
                            section["Status"] = Status.CLOSED
                    else:
                        section[column["data-th"]] = column.getText()

            section["full_name"] = section["department"] + section["course_number"]

            if section["full_name"] not in courses:
                course = Course.factory(section)
                courses[section["full_name"]] = course
            else:
                course = courses[section["full_name"]]

            if "Unique" in section and section["Unique"] is not None:
                section_obj = Section.factory(section, course)
                course.sections.append(section_obj)
                sections.append(section_obj)
                dataframe = dataframe.append(section, ignore_index=True)

                print section
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

    # levels = ["L", "U"]
    levels = ["L"]
    url_base = "https://utdirect.utexas.edu/apps/registrar/course_schedule/%s/results/?search_type_main=FIELD&fos_fl=%s&level=%s"
    df = pd.DataFrame()
    # dict of course full names (e.g. BME311) to course objects
    courses = dict()
    # list of section objects
    sections = []

    for department in departments:
        for level in levels:
            driver.get(url_base % (CATALOG_YEAR, department.replace(" ", "+"), level))
            df = append_courses(driver.page_source, df, courses, sections)
            time.sleep(3)
            # deal with paginated results
            while True:
                try:
                    next_nav_link = driver.find_element_by_id("next_nav_link")

                # for some reason it raises an exception instead of returning none if there is no such element
                except:
                    break
                driver.get(next_nav_link.get_attribute("href"))
                df = append_courses(driver.page_source, df, courses, sections)
                time.sleep(3)
    driver.close()
    # drop mysterious blank rows
    df["Unique"].replace("", np.nan, inplace=True)
    df.dropna(subset=["Unique"], inplace=True)
    print df
    df.to_csv("data_query.csv")
    return df, courses, sections


if __name__ == "__main__":
    df, courses, sections = query_catalog()
    print courses
    print len(courses)
    for course in courses.values():
        print course.sections
        print len(course.sections)
        print "\n\n"
