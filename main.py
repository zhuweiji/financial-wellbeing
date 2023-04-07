import base64
import logging
from pathlib import Path
import pickle
from typing import List, Union

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode
import altair as alt


from Categories import Category

logging.basicConfig(format='%(name)s-%(levelname)s|%(lineno)d:  %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)

AGE_GROUPS = ('Total',
 'Below 25',
 '25 - 29',
 '30 - 34',
 '35 - 39',
 '40 - 44',
 '45 - 49',
 '50 - 54',
 '55 - 59',
 '60 - 64',
 '65 & Over')

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

unique_id_count = 0
def get_new_unique_st_id(): 
    global unique_id_count
    unique_id_count+=1
    return unique_id_count

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
    d = [{'Category':i.name, 'Amount': i.get_age_group(age), 'Has Children': 'Yes' if bool(i.subcategories) else 'No'} for i in catogories]
    d = sorted(d, key=lambda x:x['Amount'], reverse=True)
    return pd.DataFrame(d)

def move_column_to_front(df, col_name, index:int):
    col = df.pop(col_name)
    df.insert(index, col_name, col)
    return df

def select_house_type():
    selected_house_type = st.selectbox('Your House', options=byhouse.columns[1:])
    df = pd.concat([byhouse['Type of Goods and Services'], byhouse[selected_house_type]], axis=1)
    df = df.rename({df.columns[1]: 'Amount'},axis=1 )
    return df,selected_house_type
    

def select_num_household():
    selected_household_size = st.select_slider('Number of people in your household', options=bynum.columns[1:], value=None)
    df = pd.concat([byincome['Type of Goods and Services'], bynum[selected_household_size]], axis=1)
    df = df.rename({df.columns[1]: 'Amount'},axis=1 )
    return df,selected_household_size
    

def select_income():
    def get_data_by_income(qtile:int):
        df = pd.concat([byincome['Type of Goods and Services'], byincome.iloc[:, 2:].iloc[:, qtile]], axis=1)
        return df.rename({df.columns[1]: 'Amount'},axis=1 )
        
    selected_income = st.selectbox('Your Individual Income Level', options=INCOME_LEVEL_TO_QTILES.keys())
    qtile = INCOME_LEVEL_TO_QTILES[selected_income]
    df = get_data_by_income(qtile)
    return df, selected_income



def main():
    expenditure_by_income,     selected_income         = select_income()
    expenditure_by_num_family, selected_household_size = select_num_household()
    expenditure_by_dwelling,   selected_house_type     = select_house_type()
    
    expenditure_by_income['Amount based on Income Quartile']     = expenditure_by_income['Amount']
    expenditure_by_income = expenditure_by_income.drop('Amount', axis=1)
    
    expenditure_by_num_family['Amount based Household Size']     = expenditure_by_num_family['Amount']
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
    
    show_underlying_data = st.checkbox('Show Underlying Data', value=False)
    displayed_df = t_df
    if not show_underlying_data:
        displayed_df = displayed_df.iloc[:,:2]
    displayed_df = st.experimental_data_editor(data=displayed_df)
    
    col1, col2 = st.columns(2)
    estimated_individual_spend = t_df['Estimated Amount'].sum()
    with col1:
        st.metric(label="Total", value=f"${estimated_individual_spend:.2f}") # show sum of above table
    with col2:
        st.metric(label="Household Total", value=f"${estimated_individual_spend * selected_household_size:.2f}") # show sum of above table
    
    # st.header('Average Monthly Household Expenditure Among Resident Households', anchor=None, help=None)
    st.subheader('Average Monthly Household Expenditure Among Resident Households', anchor=None, help='')

    spending_by_age = {'Age Group':[],'Total Amount':[]}
    for age_grp in AGE_GROUPS:
        total_spending = build_category_df__from_categories(find_by_level(0), age_grp)['Amount'].sum()
        spending_by_age['Age Group'].append(age_grp)
        spending_by_age['Total Amount'].append(total_spending)
        
    df2 = pd.DataFrame(spending_by_age)
    st.line_chart(pd.DataFrame(df2), x='Age Group', y='Total Amount')
    
    if st.checkbox('Expenditure by Category'):
        
        selected_age_group: str = st.selectbox('Age Group of Main Income Earner', AGE_GROUPS)  # type: ignore
        catogories = find_by_level(0)
        df = build_category_df__from_categories(catogories,selected_age_group)
        create_category_grid(df,selected_age_group, container_is_parent=True)
    

    

main()