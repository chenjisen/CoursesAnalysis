from typing import List, Any

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from bs4.element import Tag
import csv


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


def get_driver(website):
    driver = webdriver.Chrome()
    driver.get(website)
    return driver


class Driver:

    def __init__(self, driver=None, parent=None):
        if parent:
            self.driver = parent.driver
        else:
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
        self.parent.click_by_data_and_go_forward_to_child(data)

    def close_child_and_come_back_to_self(self):
        self.driver.close()
        self.driver.switch_to.window(self.handle)
        self.get_links()

    def close_self_and_come_back_to_parent(self):
        self.parent.close_child_and_come_back_to_self()


"""
    默认层级：上海交通大学(SJTU)、第一专业(Major)、培养计划(Program) (忽略：第二专业(Minor))
    忽略层级：学院(School)、专业类
    层级：年度(Year)-专业(Speciality)-课程类(Category)  （专业方向视为不同的专业）
    
"""


class SpecialityTableDriver(Driver):
    program_type_options: List[str]

    # 一专专业、专业类、专业方向一览表

    def __init__(self, driver):
        super(SpecialityTableDriver, self).__init__(driver=driver)

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
        category_list_driver.crawl_by_speciality(current_speciality)


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

    def __init__(self, speciality_table_driver):
        super(CategoryListDriver, self).__init__(parent=speciality_table_driver)

    def crawl_by_speciality(self, speciality):
        self.click_from_parent_by_data_and_go_forward_to_self(speciality)

        page = self.get_page()  # with open('PyjhQuery_Jb.html', encoding='UTF-8') as file: page = file.read()
        course_categories = CategoryList(page)

        for course_data in course_categories.list:
            print(course_data.name, ' ', course_data.href)

        course_table_driver = CourseTableDriver(self, speciality)

        current_category = course_categories.list[2]
        course_table_driver.crawl_by_category(current_category)

        current_category = course_categories.list[6]
        course_table_driver.crawl_by_category(current_category)

        self.close_self_and_come_back_to_parent()


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

    def __init__(self, category_list_driver, speciality):
        super(CourseTableDriver, self).__init__(parent=category_list_driver)
        self.speciality: SpecialityAttribute = speciality

    def crawl_by_category(self, category):
        self.click_from_parent_by_data_and_go_forward_to_self(category)
        page = self.get_page()
        courses = CourseTable(page)

        file_name = self.speciality.name + '-' + str(self.speciality.year) + '-' + '.csv'

        with open(file_name, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(courses.list)

        self.close_self_and_come_back_to_parent()


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

        self.number = int(td_list[0].get_text())

        code_a = td_list[1].find('a')
        if code_a:
            self.code = DataAttribute(td_list[1].get_text(), code_a['href'])
        else:
            raise Exception('Unexpected course number!')

        self.name = td_list[2].get_text()
        self.credit = int(td_list[3].get_text())
        self.credit_hour = int(td_list[4].get_text())
        self.lecture_hour = int(td_list[5].get_text())
        self.experiment_hour = int(td_list[6].get_text())
        self.practical_hour = int(td_list[7].get_text())
        self.computer_hour = int(td_list[8].get_text())
        self.design = int(td_list[9].get_text())
        self.semester = int(td_list[10].get_text())
        self.attribute = td_list[11].get_text()

        module_a = td_list[12].find('a')
        if module_a:
            self.module = DataAttribute(td_list[12].get_text(), module_a['href'])
        else:
            raise Exception('Unexpected course module!')

        self.attrs_text = []

        for td in td_list:
            self.attrs_text.append(td.get_text())


class CourseTable:
    def __init__(self, page):
        page_soup = BeautifulSoup(page, 'html.parser')
        self.table = page_soup.find('table', id='DataGrid1')
        self.list = []

        if self.table:
            for tr in self.table.find_all('tr'):
                current_course = Course(tr)
                self.list.append(current_course)
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

main_driver = get_driver(WEBSITE)  # web_driver = get_driver(LOCAL_WEBSITE)
main_speciality_table_driver = SpecialityTableDriver(main_driver)

main_speciality_table_driver.crawl_by_type_and_year(
    main_speciality_table_driver.program_type_options[0],
    main_speciality_table_driver.enrollment_year_options[3]
)

# web_driver.quit()
