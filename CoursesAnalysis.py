from typing import List, Any

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from bs4.element import Tag
import csv


class DataAttribute:
    def __init__(self, name, href):
        self.name = name
        self.href = href


class SpecialityAttribute(DataAttribute):
    def __init__(self, name, year, href, hierarchy):
        super(SpecialityAttribute, self).__init__(name, href)
        self.hierarchy = hierarchy.copy()
        self.year = year


def get_driver(website):
    driver = webdriver.Chrome()
    driver.get(website)
    return driver


class Driver:

    def __init__(self, driver, parent = None):
        self.driver = driver
        self.link_list = {}
        self.handle = None
        self.parent = parent

    def __del__(self):
        pass  # self.driver.quit()

    def get_links(self):
        links = self.driver.find_elements_by_tag_name("a")
        for link in links:
            self.link_list[link.get_attribute('href')] = link

    def click_link(self, href):
        self.link_list[href].click()

    def click_data(self, data):
        self.click_link(data.href)

    def get_page(self):
        self.handle = self.driver.current_window_handle
        self.get_links()
        return self.driver.page_source

    def quit(self):
        self.driver.quit()

    def click_by_data_and_go_forward_to_child(self, data):
        self.click_data(data)
        handles = self.driver.window_handles
        self.driver.switch_to.window(handles[-1])

    def click_from_parent_by_data_and_go_forward_to_self(self, data):
        self.parent.click_data(data)
        handles = self.driver.window_handles
        self.driver.switch_to.window(handles[-1])

    def close_new_page_and_come_back(self):
        self.driver.close()
        self.driver.switch_to.window(self.handle)
        self.get_links()


"""
    默认层级：上海交通大学(SJTU)、第一专业(Major)、培养计划(Program) (忽略：第二专业(Minor))
    忽略层级：学院(School)、专业类
    层级：年度(Year)-专业(Speciality)-课程类(Category)  （专业方向视为不同的专业）
    
"""


class SpecialityTableDriver(Driver):
    program_type_options: List[Any]

    # 一专专业、专业类、专业方向一览表

    def __init__(self, driver):
        super(SpecialityTableDriver, self).__init__(driver)

        program_type = self.driver.find_element_by_id('dpJhlx')
        enrollment_year = self.driver.find_element_by_id('dpRxnd')

        self.program_type_options = []
        program_type_list = program_type.find_elements_by_tag_name('option')
        for option in program_type_list:
            self.program_type_options.append(option.text)

        self.enrollment_year_options = []
        enrollment_year_list = enrollment_year.find_elements_by_tag_name('option')
        for option in enrollment_year_list:
            self.enrollment_year_options.append(option.text)

        self.program_type = ''
        self.enrollment_year = ''

    def query_by_name(self, type_str, year_str):

        self.program_type = type_str
        self.enrollment_year = year_str

        program_type = self.driver.find_element_by_id('dpJhlx')
        program_type_select = Select(program_type)

        enrollment_year = self.driver.find_element_by_id('dpRxnd')
        enrollment_year_select = Select(enrollment_year)

        button_query = self.driver.find_element_by_id('btnQuery')

        program_type_select.select_by_visible_text(type_str)
        enrollment_year_select.select_by_visible_text(year_str)
        button_query.click()

    def crawl_by_type_and_year(self, type_str, year_str):

        self.query_by_name(type_str, year_str)
        page = self.get_page()

        # with open('jspyjh.html', encoding='UTF-8') as file: page = file.read()

        """
            Process speciality table
        """

        title = self.enrollment_year + self.program_type
        specialities = SpecialityTable(page, int(self.enrollment_year))
        print('Speciality List: (The number of specialities: ', len(specialities.list), ')')
        for speciality in specialities.list:
            print(speciality.name, ' ', speciality.hierarchy)

        specialities.hierarchy_tree.dfs()
        specialities.hierarchy_tree.bfs()

        """
            Process speciality program course type List
        """

        category_list_driver = CategoryListDriver(self.driver)
        current_speciality: SpecialityAttribute = specialities.list[5]
        self.click_by_data_and_go_forward_to_child(current_speciality)
        category_list_driver.set_speciality(current_speciality)
        category_list_driver.crawl()
        self.close_new_page_and_come_back()


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


class CategoryListDriver(Driver):
    # 培养计划(培养目标、课程分列信息）

    def __init__(self, driver, parent_handle):
        super(CategoryListDriver, self).__init__(driver)
        self.speciality : SpecialityAttribute = None
        self.parent_handle = parent_handle

    def set_speciality(self, speciality):
        self.speciality = speciality

    def crawl(self):
        page = self.get_page()  # with open('PyjhQuery_Jb.html', encoding='UTF-8') as file: page = file.read()
        course_categories = CategoryList(page)

        for course_data in course_categories.list:
            print(course_data.name, ' ', course_data.href)

        course_table_driver = CourseTableDriver(self.driver)

        current_category = course_categories.list[2]
        self.click_by_data_and_go_forward_to_child(current_category)
        course_table_driver.set_speciality(self.speciality)
        course_table_driver.set_category(current_category)
        course_table_driver.crawl()
        self.close_new_page_and_come_back()

        current_category = course_categories.list[6]
        self.click_by_data_and_go_forward_to_child(current_category)
        course_table_driver.set_speciality(self.speciality)
        course_table_driver.set_category(current_category)
        course_table_driver.crawl()
        self.close_new_page_and_come_back()


class CategoryList:

    def __init__(self, page):

        page_soup = BeautifulSoup(page, 'html.parser')
        table = page_soup.find('table', id='Table1')
        self.list = []

        for a in table.find_all(name='a'):
            name = a.get_text()
            href = a['href']
            if name != '关闭' and name != '点击此处查看培养目标':
                self.list.append(DataAttribute(name, href))


class CourseTableDriver(Driver):
    # 培养计划课程（按类别）

    def __init__(self, driver):
        super(CourseTableDriver, self).__init__(driver)
        self.speciality = None
        self.category = None

    def set_speciality(self, speciality):
        self.speciality = speciality

    def set_category(self, category):
        self.category = category

    def crawl(self):
        page = self.get_page()
        courses = CourseTable(page)
        print(courses.table.get_text())


class CourseTable:
    def __init__(self, page):
        page_soup = BeautifulSoup(page, 'html.parser')
        self.table = page_soup.find('table', id='DataGrid1')
        self.isIdentical = True
        if not self.table:
            self.table = page_soup.find('table', id='DataGrid2')
            self.isIdentical = False

        self.list = []
        for tr in self.table.find_all('tr'):
            current_course_attrs = []
            for td in tr.find_all('td'):
                data_name = td.get_text()
                a_href = td.find(name='a')
                if a_href and data_name:
                    href = a_href['href']

                current_course_attrs.append(data_name)

            self.list.append(current_course_attrs)





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

web_driver = get_driver(WEBSITE)  # web_driver = get_driver(LOCAL_WEBSITE)
speciality_table_driver = SpecialityTableDriver(web_driver)

speciality_table_driver.crawl_by_type_and_year(
    speciality_table_driver.program_type_options[0],
    speciality_table_driver.enrollment_year_options[3]
)

# web_driver.quit()
