from typing import List, Any

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from bs4.element import Tag
import csv
import time

class DataAttribute:
    name: str
    href: str

    def __init__(self, name, href):
        self.name = name
        self.href = href


class SpecialityAttribute(DataAttribute):
    year: int
    hierarchy: List[str]

    def __init__(self, name, year, href, hierarchy):
        super(SpecialityAttribute, self).__init__(name, href)
        self.hierarchy = hierarchy.copy()
        self.year = year


class Driver:

    def __init__(self, website):
        self.driver = Driver.__get_driver(website)
        self.website = website
        self.link_list = {}

    def __del__(self):
        pass  # self.driver.quit()

    @staticmethod
    def __get_driver(website):
        driver = webdriver.Chrome()
        driver.get(website)
        return driver

    def get_links(self):
        links = self.driver.find_elements_by_tag_name("a")
        for link in links:
            self.link_list[link.get_attribute('href')] = link

    def click_link(self, href):
        self.link_list[href].click()

    def click_data(self, data):
        self.click_link(data.href)

    def get_page(self):
        # self.handle = self.driver.current_window_handle
        return self.driver.page_source

    def quit(self):
        self.driver.quit()

    def go_forward(self):
        handles = self.driver.window_handles
        self.driver.switch_to.window(handles[-1])
        self.get_links()

    def close_and_come_back(self):
        self.driver.close()
        handles = self.driver.window_handles
        self.driver.switch_to.window(handles[-1])
        self.get_links()

    def query_by_name(self, type_str, year_str):
        # SpecialityTableDriver
        program_type = self.driver.find_element_by_id('dpJhlx')
        program_type_select = Select(program_type)

        enrollment_year = self.driver.find_element_by_id('dpRxnd')
        enrollment_year_select = Select(enrollment_year)

        button_query = self.driver.find_element_by_id('btnQuery')

        program_type_select.select_by_visible_text(type_str)
        enrollment_year_select.select_by_visible_text(year_str)
        button_query.click()

        self.get_links()

    def get_type_and_year(self):
        # 一专专业、专业类、专业方向一览表
        try:
            program_type = self.driver.find_element_by_id('dpJhlx')
            enrollment_year = self.driver.find_element_by_id('dpRxnd')
            program_type_list = program_type.find_elements_by_tag_name('option')
            enrollment_year_list = enrollment_year.find_elements_by_tag_name('option')

            program_type_options = []

            for option in program_type_list:
                program_type_options.append(option.text)

            enrollment_year_options = []

            for option in enrollment_year_list:
                enrollment_year_options.append(option.text)

        except Exception as e:
            print('Error: ', format(e), 'Retrying...')
            time.sleep(5)
            self.driver.refresh()
            return self.get_type_and_year()

        else:
            return [program_type_options, enrollment_year_options]


class SpecialityTable:

    def __init__(self, page, year):

        self.year = year

        # process_speciality_table

        page_soup = BeautifulSoup(page, 'html.parser')
        table = page_soup.find('table', id='grdJxjh')

        self.list = []
        hierarchy_stack = [str(year)]
        rowspan_stack = [32767]  # sufficiently large

        self.hierarchy_tree = TreeNode(SpecialityAttribute(str(year), year, '', []), None)
        current_node = self.hierarchy_tree
        current_speciality: SpecialityAttribute

        for tr in table.find_all(name='tr', attrs={'class': 'tbshowlist'}):

            for td in tr.find_all(name='td', text=True):

                name = td.get_text()

                if 'rowspan' in td.attrs:
                    rowspan = int(td['rowspan'])
                else:
                    rowspan = 1

                a_href = td.find(name='a')
                if a_href:
                    href = a_href['href']
                else:
                    href = ''

                current_speciality = SpecialityAttribute(name, year, href, hierarchy_stack)
                current_node = current_node.add_child(current_speciality)
                hierarchy_stack.append(name)
                rowspan_stack.append(rowspan)

            self.list.append(current_speciality)

            for i in range(len(rowspan_stack)):
                rowspan_stack[i] -= 1

            while rowspan_stack[-1] == 0:
                hierarchy_stack.pop()
                rowspan_stack.pop()
                current_node = current_node.parent


class CategoryList:
    # 培养计划(培养目标、课程分列信息）
    def __init__(self, page):

        page_soup = BeautifulSoup(page, 'html.parser')
        table = page_soup.find('table', id='Table1')
        self.list = []

        for a in table.find_all(name='a'):
            name = a.get_text()
            href = a['href']
            if name != '关闭' and name != '点击此处查看培养目标':
                self.list.append(DataAttribute(name, href))

def to_int(str):
    if str == ' ':
        return 0
    return int(str)

class Course:
    """
        序号 Sequence Number
        课程代码 Course Code
        课程名称 Course Name
        学分 Credit
        学时 Credit Hour
        讲课 Lecture Hour
        实验 Experiment Hour
        实践 Practical Training Hour
        上机 Computer Operating Hour
        课程设计 Course Design
        开课学期 Semester
        课程性质 Attribute
        课程模块 Course Module
    """

    attrs_text: List[Any]

    attrs_name = ['number', 'code', 'name', 'credit',
                  'credit_hour', 'lecture_hour', 'experiment_hour', 'practical_hour', 'computer_hour',
                  'design', 'semester', 'attribute', 'module']

    number: int
    code: DataAttribute
    name: str
    credit: int
    credit_hour: int
    lecture_hour: int
    experiment_hour: int
    practical_hour: int
    computer_hour: int
    design: int
    semester: int
    attribute: str
    module: DataAttribute

    def __init__(self, tr):
        td_list: List[Tag] = tr.find_all('td')
        if len(td_list) != 13:
            raise Exception("Unexpected course data!")

        self.number = to_int(td_list[0].get_text())

        code_a = td_list[1].find('a')
        if code_a:
            self.code = DataAttribute(td_list[1].get_text(), code_a['href'])
        else:
            raise Exception('Unexpected course number!')

        self.name = td_list[2].get_text()
        self.credit = to_int(td_list[3].get_text())
        self.credit_hour = to_int(td_list[4].get_text())
        self.lecture_hour = to_int(td_list[5].get_text())
        self.experiment_hour = to_int(td_list[6].get_text())
        self.practical_hour = to_int(td_list[7].get_text())
        self.computer_hour = to_int(td_list[8].get_text())
        self.design = to_int(td_list[9].get_text())
        self.semester = to_int(td_list[10].get_text())
        self.attribute = td_list[11].get_text()

        module_a = td_list[12].find('a')
        if module_a:
            self.module = DataAttribute(td_list[12].get_text(), module_a['href'])
        else:
            raise Exception('Unexpected course module!')

        self.attrs_text = []

        for td in td_list:
            text = td.get_text()
            if text == '\xa0':
                text = ''
            self.attrs_text.append(text)


class CourseTable:
    # 培养计划课程（按类别）
    def __init__(self, page):
        page_soup = BeautifulSoup(page, 'html.parser')
        self.table = page_soup.find('table', id='DataGrid1')
        self.course_list = []
        self.course_str_list = []

        if self.table:
            tr: Tag
            for i, tr in enumerate(self.table.find_all('tr')):
                if i == 0:
                    if tr.get_text() != '\n序号课程代码课程名称学分学时讲课实验实践上机课程设计开课学期课程性质课程模块\n':
                        print(tr.get_text())
                        raise Exception('Unexpected course number!')
                else:
                    current_course = Course(tr)
                    self.course_list.append(current_course)
                    self.course_str_list.append(current_course.attrs_text)

        else:
            self.table = page_soup.find('table', id='DataGrid2')


class TreeNode:
    data: DataAttribute

    def __init__(self, data, parent):
        self.data = data
        self.parent = parent
        if parent is None:
            self.level = 0
        else:
            self.level = parent.level + 1
        self.children = []

    def add_child(self, data):
        child = TreeNode(data, self)
        self.children.append(child)
        return child

    def dfs(self):
        print(self.data.name, end='')
        if self.children:
            for child in self.children:
                print('->', end='')
                child.dfs()
        else:
            print(';')

    def bfs(self):
        hierarchy_name = ['学院列表', '学院', '所属专业类', '专业', '专业方向']

        queue = [self]
        while queue:
            node = queue.pop(0)
            if node.children:
                print('(', hierarchy_name[node.level], ')', node.data.name, end=':   ')
                for child in node.children:
                    print(child.data.name, end='; ')
                    queue.append(child)
                print()


WEBSITE = 'http://electsys.sjtu.edu.cn/edu/pyjh/pyjhQueryNew.aspx'
LOCAL_WEBSITE = 'file:///C:/Users/C/PycharmProjects/CoursesAnalysis/jspyjh_2016.html'

primal_driver = Driver(WEBSITE)

"""
    默认层级：上海交通大学(SJTU)、第一专业(Major)、培养计划(Program) (忽略：第二专业(Minor))
    忽略层级：学院(School)、专业类
    层级：年度(Year)-专业(Speciality)-课程类(Category)  （专业方向视为不同的专业）

"""

[program_type_options, enrollment_year_options] = primal_driver.get_type_and_year()

type_str = program_type_options[0]

for i1 in [3]:

    """
        Level：year
        Task: get speciality list
    """

    year_str = enrollment_year_options[i1]
    year = int(year_str)
    primal_driver.query_by_name(type_str, year_str)
    page = primal_driver.get_page()  # with open('jspyjh.html', encoding='UTF-8') as file: page = file.read()

    specialities = SpecialityTable(page, year)

    print('Speciality List: (The number of specialities: ', len(specialities.list), ')')
    for speciality in specialities.list:
        print(speciality.name, ' ', speciality.hierarchy)
    specialities.hierarchy_tree.dfs()
    specialities.hierarchy_tree.bfs()

    for i2 in [5]:

        """
            Level: speciality
            Task: get category list
        """

        current_speciality: SpecialityAttribute = specialities.list[i2]
        primal_driver.click_data(current_speciality)
        primal_driver.go_forward()
        page = primal_driver.get_page()  # with open('PyjhQuery_Jb.html', encoding='UTF-8') as file: page = file.read()

        course_categories = CategoryList(page)

        for course_data in course_categories.list:
            print(course_data.name, ' ', course_data.href)

        for i3 in [2, 6]:

            """
                Level: category
                Task: get course list
            """

            current_category = course_categories.list[i3]
            file_name = current_speciality.name\
                        + '-' + str(current_speciality.year) \
                        + '-' + str(current_category.name) \
                        + '.csv'
            primal_driver.click_data(current_category)
            primal_driver.go_forward()
            page = primal_driver.get_page()

            courses = CourseTable(page)

            print(courses.table.get_text())

            if courses.course_str_list:
                with open(file_name, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerows(courses.course_str_list)

            primal_driver.close_and_come_back()

        primal_driver.close_and_come_back()


# web_driver.quit()


'''primal_driver = Driver('file:///C:/Users/C/PycharmProjects/CoursesAnalysis/PyjhQuery_Fl.html')
page = primal_driver.get_page()
courses = CourseTable(page)

print(courses.table.get_text())

if courses.course_str_list:
    with open('test.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(courses.course_str_list)'''
