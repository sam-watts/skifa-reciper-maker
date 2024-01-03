import streamlit as st
import numpy as np
import pandas as pd
import re

debug = False

st.set_page_config(
    page_title="SKIFA Reciper Scaler",
    page_icon="🌍️",
    initial_sidebar_state="expanded",
    layout="wide",
)

    
col_left_input, _ = st.columns([0.4, 0.6], gap="medium")

with col_left_input:
    master_scaling_factor = st.number_input(
        "Master Scaling Factor", min_value=1, max_value=100, value=1, step=1
    )

col_left, col_right = st.columns([0.4, 0.6], gap="medium")

unit_conversions = dict(
    kg=1,
    g=0.001,
    ml=0.001,
    l=1,
    lt=1,
)

green_city = pd.read_csv("SKIFA Price sheet - Greencity_Wholefoods_Pricelist.csv")
green_city.columns = [x.lower().replace(" ", "_") for x in green_city.columns]

green_city = green_city.rename(columns=dict(trade_price_as_of_12_june_2023="trade_price"))

with st.expander("Full green city pricelist search"):
    gc_search_term = st.text_input("Search the pricelist by ingredient name...")
    st.dataframe(green_city[green_city["description"].str.lower().str.contains(gc_search_term.lower())])

row_template = {
    "ingredient": "",
    "amount": 0,
    "unit": "",
    "manual_ingredient_selector": None,
}

df = pd.DataFrame(
    [row_template.copy() for i in range(10)]
)

df["manual_ingredient_selector"] = df["manual_ingredient_selector"].astype("category").cat.add_categories(green_city["description"].unique())

with col_left:
    st.text("Input ingredients data here:")
    edited_df = st.data_editor(df, num_rows="dynamic")

edited_df["scaling_factor"] = 1 * master_scaling_factor
edited_df["scaled_amount"] = (edited_df["amount"] * edited_df["scaling_factor"]).astype(str) + edited_df["unit"]

if debug:
    st.dataframe(edited_df)

ingredient_matcher = []
for i, row in edited_df.iterrows():
    if row["ingredient"] in (None, "") and pd.isna(row["manual_ingredient_selector"]):
        continue
    
    if row["manual_ingredient_selector"] is np.NaN:
        query = row["ingredient"].lower()
        query = "".join([f"(?=.*{x})" for x in query.split()]) + ".*$"
        temp = green_city[green_city["description"].str.lower().str.contains(query)]
        temp["manually_selected"] = False
    else:
        temp = green_city[green_city["description"] == row["manual_ingredient_selector"]]
        temp["manually_selected"] = True
        
    temp["origin_index"] = i
    temp["ingredient"] = row["ingredient"]
    temp["amount"] = row["amount"] * row["scaling_factor"]
    temp["unit"] = row["unit"]
    
    ingredient_matcher.append(temp)
    
ingredient_matcher = pd.concat(ingredient_matcher)

ingredient_matcher["gc_amount"] = ingredient_matcher["size"].apply(lambda x: float(re.findall("\d+\.?\d*", x)[0]))
ingredient_matcher["gc_unit"] = ingredient_matcher["size"].apply(lambda x: re.findall("[a-zA-Z]+", x)[0])
ingredient_matcher["pack_amount"] = ingredient_matcher["gc_amount"] * ingredient_matcher["pack_size"]
ingredient_matcher["pack_normed"] = ingredient_matcher["pack_amount"] * ingredient_matcher["gc_unit"].apply(lambda x: unit_conversions.get(x, 1))
ingredient_matcher["pounds_per_pack_normed"] = ingredient_matcher["pack_normed"] / ingredient_matcher["trade_price"]
ingredient_matcher["amount_excess"] = ingredient_matcher["pack_normed"] - ingredient_matcher["amount"] 
ingredient_matcher["enough_food"] = ingredient_matcher["amount_excess"] > 0
ingredient_matcher["price_rank"] = ingredient_matcher.groupby(["origin_index", "enough_food"])["pounds_per_pack_normed"].rank(method="min")
ingredient_matcher["order_quantity"] = 1 # this will be the only value for now - need to create more rows with multiples
ingredient_matcher["line_total"] = ingredient_matcher["order_quantity"] * ingredient_matcher["trade_price"]
ingredient_matcher.loc[~ingredient_matcher["enough_food"], "price_rank"] = np.NaN

ingredient_matcher.loc[ingredient_matcher["manually_selected"], "price_rank"] = 0

with col_right:
    st.text("Picked ingredients:")
    if debug:
        st.text("debug"); ingredient_matcher
    chosen_ingredients = (
        ingredient_matcher[ingredient_matcher["enough_food"]]
        .sort_values("price_rank")
        .groupby("origin_index")
        .head(1)
        .sort_values("origin_index")
        .reset_index(drop=True)
        # [["description", "pack_size", "size", "trade_price", "order_quantity", "line_total"]]
    )
    # in cases where an origin index has no adequate matching ingredients, we need to add
    # a placeholder row that says "ingredient not found"
    missing_indices = set(edited_df[(edited_df["ingredient"] != "") | (edited_df["ingredient"].isnull())| (edited_df["manual_ingredient_selector"].notna())].index) - set(chosen_ingredients["origin_index"])

    chosen_ingredients = pd.concat([
        chosen_ingredients,
        pd.DataFrame([{
            "origin_index": i,
            "description": "Ingredient not found",
            "pack_size": np.NaN,
            "size": np.NaN,
            "trade_price": np.NaN,
            "order_quantity": np.NaN,
            "line_total": np.NaN,
        } for i in missing_indices])
    ]).sort_values("origin_index").reset_index(drop=True)
    
    chosen_ingredients[["description", "pack_size", "size", "trade_price", "order_quantity", "line_total"]]
    
    if not chosen_ingredients.empty:
        st.text("Total cost: £" + str((chosen_ingredients["trade_price"] * chosen_ingredients["order_quantity"]).sum()))

# TODO also apply conversions to input table

with st.expander("TODOs"):
    st.text("""
    - [x] Add checking against buying multiple smaller packs vs. one bigger pack
    """)