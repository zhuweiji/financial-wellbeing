import base64
import logging
from pathlib import Path
import pickle
import re
from typing import List, Union
from attr import dataclass

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode
import altair as alt

from Categories import Category

logging.basicConfig(format='%(name)s-%(levelname)s|%(lineno)d:  %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

APP_NAME = 'FinSight'

st.set_page_config(
    page_title=APP_NAME,
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'https://www.extremelycoolapp.com/help',
        # 'Report a bug': "https://www.extremelycoolapp.com/bug",
        # 'About': ""
    }
)

AGE_GROUPS = ('Average',
 'Below 25',
 '25 - 29',
 '30 - 34',
 '35 - 39',
 '40 - 44',
 '45 - 49',
 '50 - 54',
 '55 - 59',
 '60 - 64',
 '65 & Over'
 )

AGE_GRP_TO_SPENDING_MUL = {
    'Average':  1.016276,
    'Below 25': 0.846914,
    '25 - 29':  0.924125,
    '30 - 34': 1.043092,
    '35 - 39': 1.121353,
    '40 - 44': 1.22865,
    '45 - 49': 1.16569,
    '50 - 54': 1.17853,
    '55 - 59': 0.996156,
    '60 - 64': 0.832904,
    '65 & Over': 0.646313,
}

INCOME_LEVEL_TO_QTILES = {
  'Below 500'    :  0,
  '500 - 999'    :  0,
  '1,000 - 1,499':  1,
  '1,500 - 1,999':   1,
  '2,000 - 2,499':   2,
  '2,500 - 2,999':   2,
  '3,000 - 3,499':   2,
  '3,500 - 3,999':   3,
  '4,000 - 4,499':   3,
  '4,500 - 4,999':   3,
  '5,000 - 5,499':   3,
  '5,500 - 5,999':   4,
  '6,000 - 6,999':   4,
  '7,000 - 7,999':   4,
  '8,000 - 8,999':   4,
  '9,000 & Over ':   4,
}

cwd = Path(__file__).parent


@st.cache_resource
def load_data():
    def remove_rows_that_are_totals(df): return df[df['Type of Goods and Services'].map(lambda x: 'total' not in x.lower())]
    bynum    = remove_rows_that_are_totals(pd.read_excel('per-household-member-bynum.xlsx'))
    byhouse  = remove_rows_that_are_totals(pd.read_excel('per-household-member-bydwelling.xlsx'))
    byincome = remove_rows_that_are_totals(pd.read_excel('per-household-member-byincome.xlsx'))
    
    with open(cwd / 'singstat-avg-household-exp.pickle', 'rb') as f:
        data = pickle.load(f)
        
    return bynum,byhouse,byincome,data



bynum,byhouse,byincome,data = load_data()

data = [i for i in data if 'total' not in i.name.lower() ]

def find_by_level(level:int) -> List["Category"]:
    return [i for i in data if i.level == level]

def find_by_name(name:str) -> "Category":
    return [i for i in data if i.name == name][0]    


def create_category_grid(df: pd.DataFrame, selected_age_group: str, container_is_parent=False):
    def get_category_selected(grid_response) -> Union[str,None]: 
        if grid_response.selected_rows: return grid_response.selected_rows[0]['Category'] 
    
    current_category = find_by_name(df['Category'].iloc[0])
    parent = current_category.parent_category 
    plot_name = f'{parent.name.title() if parent else "All"} Expenditures'
    st.header(plot_name, anchor=None, help='')
    
    if st.checkbox(f'Show Plot for {plot_name}', value=True):
        st.bar_chart(df, x='Category',y='Amount')

    gb = GridOptionsBuilder.from_dataframe(df)
    
    gb.configure_pagination(paginationAutoPageSize=True) #Add pagination
    gb.configure_side_bar() #Add a sidebar
    gb.configure_selection()
    gridOptions = gb.build()
    
    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        data_return_mode=DataReturnMode.AS_INPUT, 
        update_mode=GridUpdateMode.MODEL_CHANGED, 
        fit_columns_on_grid_load=False,
        enable_enterprise_modules=True,
        height=350, 
        width='50%',
        reload_data=True
    )
    if df['More details'].map(lambda i: i=='Yes').any():
        st.caption('Some categories in the table may contain subcategories. You may further expand these categories by clicking on them.')
    
    st.metric(label="Total", value=f"${df['Amount'].sum():.2f}") # show sum of above table

        
    category_name = get_category_selected(grid_response)
    
    def show_subgrid():
        if category_name:
            category = find_by_name(category_name)
            children = category.subcategories
            if children:
                children_df = build_category_df__from_categories(children,selected_age_group)
                create_category_grid(children_df, selected_age_group)
    
    if container_is_parent:
        with st.expander("More details"): 
            show_subgrid()
    else: show_subgrid()


def build_category_df__from_categories(catogories: List[Category], age):
    d = [{'Category':i.name, 'Amount': i.get_age_group(age), 'More details': 'Yes' if bool(i.subcategories) else 'No'} for i in catogories]
    d = sorted(d, key=lambda x:x['Amount'], reverse=True)
    return pd.DataFrame(d)

def move_column_to_front(df, col_name, index:int):
    col = df.pop(col_name)
    df.insert(index, col_name, col)
    return df


def IndividualExpenditurePage():
    container = st.container()
    
    def select_num_household():
        selected_household_size = container.select_slider('Number of people in your household', options=bynum.columns[1:], value=None)
        df = pd.concat([byincome['Type of Goods and Services'], bynum[selected_household_size]], axis=1)
        df = df.rename({df.columns[1]: 'Amount'},axis=1 )
        return df,selected_household_size
    

    def select_income():
        def get_data_by_income(qtile:int):
            df = pd.concat([byincome['Type of Goods and Services'], byincome.iloc[:, 2:].iloc[:, qtile]], axis=1)
            return df.rename({df.columns[1]: 'Amount'},axis=1 )
        
        selected_income = container.selectbox('Your Individual Income Level (after CPF)', options=INCOME_LEVEL_TO_QTILES.keys(), index=4)
        qtile = INCOME_LEVEL_TO_QTILES[selected_income]
        df = get_data_by_income(qtile)
        return df, selected_income
    
    def select_house_type():
        selected_house_type = container.selectbox('Your House', options=byhouse.columns[1:], index=4)
        df = pd.concat([byhouse['Type of Goods and Services'], byhouse[selected_house_type]], axis=1)
        df = df.rename({df.columns[1]: 'Amount'},axis=1 )
        return df,selected_house_type
    
    def select_age_grp():
        selected_age_grp = container.selectbox('Your Age Group', options=AGE_GROUPS, index=2)
        return selected_age_grp

    container.header('Estimated Individual/Household Spend')
    container.markdown("""
Discover personalized spending estimates and forecasts tailored to your unique financial situation.
""")
    container.markdown('<br/>', unsafe_allow_html=True)
    
    container.markdown("""
Input your individual income level, the number of people in your household, and your type of residence to get an accurate projection of your spending habits across various categories.

This information empowers you to make informed financial decisions and plan for the future with confidence.""")
    
    container.divider()
    container.markdown('<br/>', unsafe_allow_html=True)
    container.markdown('<br/>', unsafe_allow_html=True)


    selected_age_grp                                   = select_age_grp()
    container.markdown('<br>', unsafe_allow_html=True)
    expenditure_by_income,     selected_income         = select_income()
    container.markdown('<br>', unsafe_allow_html=True)
    expenditure_by_num_family, selected_household_size = select_num_household()
    container.markdown('<br>', unsafe_allow_html=True)
    expenditure_by_dwelling,   selected_house_type     = select_house_type()
    container.markdown('<br/>', unsafe_allow_html=True)
    container.markdown('<br/>', unsafe_allow_html=True)
    container.markdown('<br/>', unsafe_allow_html=True)
    
    
    expenditure_by_income['Amount based on Income Quartile']     = expenditure_by_income['Amount']
    expenditure_by_income = expenditure_by_income.drop('Amount', axis=1)
    
    expenditure_by_num_family['Amount based on Household Size']     = expenditure_by_num_family['Amount']
    expenditure_by_num_family = expenditure_by_num_family.drop('Amount', axis=1)
    expenditure_by_num_family = expenditure_by_num_family.drop('Type of Goods and Services', axis=1)
    
    expenditure_by_dwelling['Amount based on Dwelling Type']     = expenditure_by_dwelling['Amount']
    expenditure_by_dwelling = expenditure_by_dwelling.drop('Amount', axis=1)
    expenditure_by_dwelling = expenditure_by_dwelling.drop('Type of Goods and Services', axis=1)
    
    try:
        selected_household_size = int(selected_household_size)
    except ValueError:
        selected_household_size = 3
    
    t_df = pd.concat([expenditure_by_income, expenditure_by_num_family, expenditure_by_dwelling],axis=1)
    t_df['Estimated Amount'] = t_df.iloc[:, 1:].mean(axis=1)
    t_df['Estimated Amount'] = t_df['Estimated Amount'].round(2)
    t_df = move_column_to_front(t_df, 'Estimated Amount', 1)
    
    show_underlying_data = container.checkbox('Show Underlying Data', value=False)
    displayed_df = t_df
    if not show_underlying_data:
        displayed_df = displayed_df.iloc[:,:2]
    displayed_df = container.experimental_data_editor(data=displayed_df, use_container_width=True)
    
    container.caption('You can change any of the amounts in the table to reflect your actual spending, and the totals will be updated.')
    container.caption('For example, if you spent 300 on food last month, double click on the value in *Estimated Amount* and update the value to 300.')
    container.caption('You can dive into what goes into each category of expenditure in the *Household Expenditure* page')
    
    
    estimated_individual_spend = displayed_df['Estimated Amount'].sum()
    # existing_age_scale_factor = AGE_GRP_TO_SPENDING_MUL.get(selected_age_grp, 1)
    # estimated_individual_spend = estimated_individual_spend * existing_age_scale_factor
    
    container.markdown('<br/>', unsafe_allow_html=True)
    container.markdown('<br/>', unsafe_allow_html=True)
    col0, col1, col2 = st.columns(3)
    
    container.header('Estimated Individual/Household Spend')
    container.markdown('<br/>', unsafe_allow_html=True)
    container.divider()
    
    def get_delta_from_prev_spend(idx):
        get_prev_spending_key = lambda idx: f'prev_spend_value|{idx}'
        key = get_prev_spending_key(idx=idx)
        prev_val = st.session_state.get(key,None)
        st.session_state[key] = estimated_individual_spend
        return estimated_individual_spend-prev_val if prev_val else 0
    
    with col0:
        st.subheader('Current')
    with col1:
        delta = get_delta_from_prev_spend(0)
        st.metric(label="Estimated Total", value=f"${estimated_individual_spend:.2f}", delta=f'{delta:.2f}') # show sum of above table
            
    with col2:
        delta = get_delta_from_prev_spend(1)
        st.metric(label="Estimated Household Total", value=f"${estimated_individual_spend * selected_household_size:.2f}", delta=f'{delta:.2f}') # show sum of above table
    st.divider()

    
    start_age, end_age, existing_age_scale_factor = None, None, None
    if selected_age_grp:
        match_obj = re.search(r'(\d+) - (\d+)', selected_age_grp)
        if match_obj:
            groups = match_obj.groups()
            if len(groups) == 2:
                start_age, end_age = groups
                start_age, end_age = int(start_age), int(end_age)
                existing_age_scale_factor = AGE_GRP_TO_SPENDING_MUL.get(selected_age_grp, None)
    
    if start_age and end_age and existing_age_scale_factor:
        idx = 2
        for header, age_delta in (
            ('Five Years Time', 5),
            ('Ten Years Time', 10),
            ('Twenty Years Time', 20),
        ):
            new_age_grp = f'{start_age + age_delta} - {end_age + age_delta}'
            new_grp_scale_factor = AGE_GRP_TO_SPENDING_MUL.get(new_age_grp, None)
            if new_grp_scale_factor:
                scale_factor = new_grp_scale_factor/existing_age_scale_factor
                estimated_spend = estimated_individual_spend * scale_factor
                
                col0, col1, col2 = st.columns(3)
                with col0:
                    st.subheader(header)
                    st.caption(f'Age group: {new_age_grp}')
                with col1:
                    st.metric(label="Estimated Total", value=f"${estimated_spend:.2f}") # show sum of above table
                with col2:
                    st.metric(label="Estimated Household Total", value=f"${estimated_spend * selected_household_size:.2f}") # show sum of above table
                    
                st.divider()
            

    return container


def IntroPage():
    container = st.container()
    md_text = f"""
# Hello! 
Welcome to {APP_NAME}!
We are a one-stop platform that offers insights into personal and household expenditure trends in Singapore, helping you to make better financial decisions for your future.

Our website features two essential tools that provide detailed analysis and forecasts on expenditure patterns based on your individual and household characteristics.

---

### Personal Expenditure:
Discover how your individual income level, the number of people in your household, and your type of residence affect your spending habits.

Our Personal Expenditure tool estimates the average amount spent on various goods and services like food, clothing, and housing, tailored to your unique situation.

Additionally, it provides forecasts of your expenditure over the next 5, 10, and 20 years, giving you a clear understanding of how your spending patterns may change over time.

---

### Household Expenditure:
Explore the average monthly expenditure of Singaporean households with a comprehensive graph illustrating the relationship between the age group of the main breadwinner and total household spending.

The expenditure is broken down by category and delves into three levels of depth (e.g., Misc -> Insurance -> Health insurance). This detailed analysis helps you understand the nuances of household expenditure patterns in Singapore.

Start your financial planning journey today with {APP_NAME} and gain valuable insights into your personal and household expenditure trends!
    """
    
    container.markdown(md_text)
    
    return container



def main():
    
    with st.sidebar:
        HOME_PAGE_Selected = st.button('Home Page') 
        INDIVIDUAL_PAGE_Selected = st.button('Personal Expenditure') 
        HOUSEHOLD_PAGE_Selected = st.button('Household Expenditure') 
        
        if HOME_PAGE_Selected:
            HOUSEHOLD_PAGE_Selected = False
            HOUSEHOLD_PAGE_Selected = False
            st.session_state['HOUSEHOLD_PAGE_Selected'] = False
            st.session_state['INDIVIDUAL_PAGE_Selected'] = False
            
            st.session_state['HOME_PAGE_Selected'] = True
        
        elif INDIVIDUAL_PAGE_Selected:
            HOUSEHOLD_PAGE_Selected = False
            HOME_PAGE_Selected = False
            
            st.session_state['HOUSEHOLD_PAGE_Selected'] = False
            st.session_state['HOME_PAGE_Selected'] = False
            
            st.session_state['INDIVIDUAL_PAGE_Selected'] = True
            
            
        elif HOUSEHOLD_PAGE_Selected:
            INDIVIDUAL_PAGE_Selected = False
            HOME_PAGE_Selected = False
            
            st.session_state['INDIVIDUAL_PAGE_Selected'] = False
            st.session_state['HOME_PAGE_Selected'] = False
            
            st.session_state['HOUSEHOLD_PAGE_Selected'] = True
            
        HOME_PAGE_Selected       = HOME_PAGE_Selected or  st.session_state.get('HOME_PAGE_Selected', False) 
        INDIVIDUAL_PAGE_Selected = INDIVIDUAL_PAGE_Selected or  st.session_state.get('INDIVIDUAL_PAGE_Selected', False) 
        HOUSEHOLD_PAGE_Selected  = HOUSEHOLD_PAGE_Selected  or  st.session_state.get('HOUSEHOLD_PAGE_Selected', False) 
        
        st.session_state['INDIVIDUAL_PAGE_Selected'] = INDIVIDUAL_PAGE_Selected
    
    if not any(
        [HOME_PAGE_Selected, INDIVIDUAL_PAGE_Selected, HOUSEHOLD_PAGE_Selected]
    ):
        HOME_PAGE_Selected = True
    
    if HOME_PAGE_Selected:
        IntroPage()
    elif INDIVIDUAL_PAGE_Selected:
        IndividualExpenditurePage()
    
    elif HOUSEHOLD_PAGE_Selected:
        st.header('Explore Household Expenditure by Category')
        st.write("Delve into what goes into the typical Singaporean household's expenditure.")
        # st.write("Delve into the average monthly spending habits of Singaporean households using our informative graph, which showcases the connection between the age group of the primary income earner and the overall household expenses.")
        st.write("Our detailed breakdown of expenditure categories dives into three levels of depth (e.g., Misc -> Insurance -> Health insurance) to give you a better understanding of the intricacies of household spending patterns in Singapore.")
        st.markdown('<br/>', unsafe_allow_html=True)
        st.markdown('<br/>', unsafe_allow_html=True)

        # the lines for if age_grp == 'Average': age_grp = 'Total' is because the data is stored in a pickle file and we want to rename the Total Column to Average but did not recreate the pickle file
        
        spending_by_age_df = {'Age Group':[],'Total Amount':[]}
        for age_grp in AGE_GROUPS:
            if age_grp == 'Average': age_grp = 'Total'
            total_spending = build_category_df__from_categories(find_by_level(0), age_grp)['Amount'].sum()
            if age_grp == 'Total': age_grp = 'Average'
            spending_by_age_df['Age Group'].append(age_grp)
            spending_by_age_df['Total Amount'].append(total_spending)
            
            
        spending_by_age_df = pd.DataFrame(spending_by_age_df)
        
        st.subheader('Average Monthly Household Expenditure Among Resident Households', anchor=None, help='')
        st.caption('This chart shows the average monthly expenditure by households for different ages of the main breadwinner.')
        st.line_chart(spending_by_age_df, x='Age Group', y='Total Amount')
        
        if st.checkbox('View Expenditure by Category'):
            st.caption('Delve into the different categories that make up the total household expenditure')
            
            selected_age_group: str = st.selectbox('Age Group of Main Income Earner', AGE_GROUPS)  # type: ignore
            catogories = find_by_level(0)
            if selected_age_group == 'Average': selected_age_group = 'Total'
            
            df = build_category_df__from_categories(catogories,selected_age_group)
            create_category_grid(df,selected_age_group, container_is_parent=True)
        

main()