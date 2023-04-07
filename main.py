import base64
import logging
from pathlib import Path
import pickle
from typing import List, Union

import numpy as np
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode

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

cwd = Path(__file__).parent

with open(cwd / 'singstat-avg-household-exp.pickle', 'rb') as f:
    data = pickle.load(f)

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

# col1, col2 = st.columns(2)

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


def main():
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