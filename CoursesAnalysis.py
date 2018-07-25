from typing import List, Any, Dict, TextIO

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from bs4.element import Tag
import csv
import time


class DataOnPage:
    name: str
    href: str

    def __init__(self, name, href):
        self.name = name
        self.href = href


class SpecialityOnPage(DataOnPage):
    year: int
    hierarchy: List[str]

    def __init__(self, name, year, href, hierarchy=None):
        super(SpecialityOnPage, self).__init__(name, href)
        if hierarchy:
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

    def get_url(self):
        return self.driver.current_url

    def get_links(self):
        links = self.driver.find_elements_by_tag_name("a")
        for link in links:
            self.link_list[link.get_attribute('href')] = link

    def click_link(self, href):
        try:
            self.link_list[href].click()
        except Exception as e:
            print('Error: ', format(e), 'Retrying...')
            time.sleep(5)
            self.driver.refresh()

    def click_data_and_go_forward(self, data):
        self.click_link(data.href)
        handles = self.driver.window_handles
        self.driver.switch_to.window(handles[-1])
        self.get_links()

    def get_page(self):
        # self.handle = self.driver.current_window_handle
        return self.driver.page_source

    def quit(self):
        self.driver.quit()

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

        self.hierarchy_tree = TreeNode(SpecialityOnPage(str(year), year, '', []), None)
        current_node = self.hierarchy_tree
        current_speciality: SpecialityOnPage

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

                current_speciality = SpecialityOnPage(name, year, href, hierarchy_stack)
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
                self.list.append(DataOnPage(name, href))


def to_int(string):
    if string == ' ':
        return 0
    return int(string)


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
    code: DataOnPage
    name: str
    credit: float
    credit_hour: int
    lecture_hour: int
    experiment_hour: int
    practical_hour: int
    computer_hour: int
    design: int
    semester: int
    attribute: str
    module: DataOnPage

    def __init__(self, tr):
        td_list: List[Tag] = tr.find_all('td')
        if len(td_list) != 13:
            raise Exception("Unexpected course data!")

        self.number = to_int(td_list[0].get_text())

        code_a = td_list[1].find('a')
        if code_a:
            self.code = DataOnPage(td_list[1].get_text(), code_a['href'])
        else:
            raise Exception('Unexpected course number!')

        self.name = td_list[2].get_text()
        self.credit = float(td_list[3].get_text())
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
            self.module = DataOnPage(td_list[12].get_text(), module_a['href'])
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
    data: DataOnPage

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


class SpecialityInfo:
    year: int
    name: str
    url: str

    def __init__(self, year, name, url):
        self.year = year
        self.name = name
        self.url = url
        self.label = str(self.year) + self.name


class SpecialityState:
    # url: str
    speciality: SpecialityInfo
    date_time: str

    # is_completed: bool

    def __init__(self, info: SpecialityInfo):
        self.speciality = info
        self.date_time = time.strftime("%Y-%m-%d,%H:%M:%S", time.localtime())
        # self.is_completed = bool(str_is_completed)

    def to_str(self):
        return self.speciality.label \
               + ' ' + self.speciality.url \
               + ' ' + self.date_time + '\n'


class StateDict:
    # record the state which speciality is crawled
    # only consider major
    # str format: [year + name] : url time

    dict: Dict[str, SpecialityState]
    file: TextIO

    def __init__(self, file_name):
        self.dict = {}
        self.file = open(file_name, 'r+')
        for line in self.file.readlines():
            # format: year+name url datetime
            args = line.split()
            year = int(args[0][:4])
            name = args[0][4:]
            url = args[1]
            info = SpecialityInfo(year, name, url)
            state = SpecialityState(info)
            self.dict.setdefault(info.label, state)

    def add(self, speciality: SpecialityOnPage, url):
        info = SpecialityInfo(speciality.year, speciality.name, url)
        state = SpecialityState(info)
        self.dict.setdefault(info.label, state)
        self.file.write(state.to_str())

    def find(self, speciality: SpecialityOnPage):
        return str(speciality.year) + speciality.name in self.dict

    def __del__(self):
        self.file.close()


WEBSITE = 'http://electsys.sjtu.edu.cn/edu/pyjh/pyjhQueryNew.aspx'
LOCAL_WEBSITE = 'file:///C:/Users/C/PycharmProjects/CoursesAnalysis/jspyjh_2016.html'

state_dict = StateDict('files\state.txt')
category_file = open('files\category.txt', 'a')

primal_driver = Driver(WEBSITE)

"""
    默认层级：上海交通大学(SJTU)、第一专业(Major)、培养计划(Program) (忽略：第二专业(Minor))
    忽略层级：学院(School)、专业类
    层级：年度(Year)-专业(Speciality)-课程类(Category)  （专业方向视为不同的专业）

"""
"""
    网址格式：
    专业：
    最近：
    http://electsys.sjtu.edu.cn/edu/pyjh/pyjhquery2009.aspx?zydm=[代码]&mc=[专业]&nj=[年度]
    (更久之前：
    http://electsys.sjtu.edu.cn/edu/pyjh/pyjhquery_jb.aspx?zydm=[代码]&mc=[专业]&nj=[年度])
    课程类：
    http://electsys.sjtu.edu.cn/edu/pyjh/PyjhQuery_Fl.aspx?kclbm=[课程类编码]&nj=[年度]&zydm=[代码]
    &pyid=[?]&pyxh=[?]&zypyxh=&zylx=[?]&mc=[专业][年度]级培养计划[课程类]课程
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
    # specialities.hierarchy_tree.dfs()
    # specialities.hierarchy_tree.bfs()

    for i2 in range(4):

        """
            Level: speciality
            Task: determine whether the speciality has been crawled
        """

        current_speciality: SpecialityOnPage = specialities.list[i2]
        if not state_dict.find(current_speciality):
            """
                Task: get category list
            """
            primal_driver.click_data_and_go_forward(current_speciality)
            page = primal_driver.get_page()
            course_categories = CategoryList(page)

            # for category in course_categories.list: print(category.name, ' ', category.href)
            category_info_list = []
            for category in course_categories.list:

                """
                    Level: category
                    Task: get course list
                """
                category_label = str(current_speciality.year) \
                                 + '-' + current_speciality.name \
                                 + '-' + category.name
                file_name = 'files\\' + category_label + '.csv'
                primal_driver.click_data_and_go_forward(category)
                page = primal_driver.get_page()

                courses = CourseTable(page)

                # print(courses.table.get_text())

                if courses.course_str_list:
                    with open(file_name, 'w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerows(courses.course_str_list)

                    category_info = str(current_speciality.year) \
                                    + ' ' + current_speciality.name \
                                    + ' ' + category.name \
                                    + ' ' + primal_driver.get_url() + '\n'
                    category_info_list.append(category_info)

                primal_driver.close_and_come_back()

            category_file.writelines(category_info_list)
            state_dict.add(current_speciality, primal_driver.get_url())

            primal_driver.close_and_come_back()

            # mark that the speciality is crawled

# web_driver.quit()

category_file.close()
