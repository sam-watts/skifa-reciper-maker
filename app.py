import streamlit as st
import numpy as np
import pandas as pd
import re

debug = True

st.set_page_config(
    page_title="SKIFA Reciper Scaler",
    page_icon="✊",
    initial_sidebar_state="expanded",
    layout="wide",
)

    
col_left_input, _ = st.columns([0.4, 0.6], gap="medium")

with col_left_input:
    input_split = st.columns([0.5, 0.5])
    with input_split[0]:
        original_recipe_servings = st.number_input(
            "Original Recipe Servings", min_value=1, max_value=100, value=1, step=1
        )
    with input_split[1]:
        desired_recipe_servings = st.number_input(
            "Desired Recipe Servings", min_value=1, max_value=100, value=1, step=1
        )
        master_scaling_factor = desired_recipe_servings / original_recipe_servings

col_left, col_right = st.columns([0.35, 0.65], gap="medium")

unit_conversions = dict(
    kg=1,
    g=0.001,
    ml=0.001,
    l=1,
    lt=1,
    tbsp=0.015,
    tsp=0.005,
    cup=0.25,
)

fresh_produce = pd.DataFrame([
    ("@Courgette", 0.29, 0.6, None),
    ("@Medium onion", 0.2, 0.14, None),
    ("@Butternut squash medium", 0.7, 1.50, None),
    ("@Fresh tomatoes", 0.08, 0.16, None),
    ("@Leek", 0.3, 0.5, None),
    ("@Potato medium", 0.25, 0.25, None),
    ("@Celeriac", 0.9, 1.3, None),
    ("@Carrot", 0.061, 0.1, None),
    ("@Celery head", 0.5, 1.5, None),
    ("@Kale", 0.25, 1.5, None),
    ("@Broccoli", 0.35, 1.3, None),
    ("@Lettuce", 0.3, 1.2, None),
    ("@White cabbage", 0.8, 1.2, None),
    ("@Red cabbage", 0.5, 1.2, None),
    ("@Peas", None, None, 3.12),
    ("@Green beans", None, None, 1.40),
    ("@Apple", 0.2,  0.3, None),
], columns=["description", "single_weight_kg", "each_price_pounds", "price_per_kg"])

fresh_produce.loc[fresh_produce["price_per_kg"].isna(), "price_per_kg"] = fresh_produce["each_price_pounds"] / fresh_produce["single_weight_kg"]

with st.expander("Fresh produce price list"):
    st.dataframe(
        fresh_produce,
        column_config={"single_weight_kg": {"format": "{:.2f} kg"}, "each_price_pounds": {"format": "£{:.2f}"}},
    )

green_city = pd.read_csv("SKIFA Price sheet - Greencity_Wholefoods_Pricelist.csv")
green_city.columns = [x.lower().replace(" ", "_") for x in green_city.columns]

green_city = green_city.rename(columns=dict(trade_price_as_of_12_june_2023="trade_price"))

green_city["order_quantity"] = 1

multiples = 5

for i in range(2, multiples+1):
    multiply = green_city.copy()
    multiply["order_quantity"] = i
    green_city = pd.concat([green_city, multiply])

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

df["manual_ingredient_selector"] = df["manual_ingredient_selector"].astype("category").cat.add_categories(
    np.concatenate([
        green_city["description"].unique(),
        fresh_produce["description"],
    ])
)

with col_left:
    st.text("Input ingredients data below:")
    edited_df = st.data_editor(df, num_rows="dynamic")
    st.markdown("Add ingredient, quantity and unit (eg. kg) and a matching ingredient will be shown in the right column from the green city price list. `manual_ingredient_selector` can be used to manually select an ingredient from the price list via search")

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
    elif "@" in row["manual_ingredient_selector"]:
        temp = fresh_produce[fresh_produce["description"] == row["manual_ingredient_selector"]]
        temp["manually_selected"] = True
    else:
        temp = green_city[green_city["description"] == row["manual_ingredient_selector"]]
        temp["manually_selected"] = True
        
    temp["origin_index"] = i
    temp["ingredient"] = row["ingredient"]
    temp["amount"] = row["amount"] * row["scaling_factor"]
    temp["unit"] = row["unit"]
    
    ingredient_matcher.append(temp)
    
st.dataframe(pd.concat(ingredient_matcher))

ingredient_matcher = pd.concat(ingredient_matcher)
ingredient_matcher_manual = ingredient_matcher[ingredient_matcher["manually_selected"]]
ingredient_matcher = ingredient_matcher[~ingredient_matcher["manually_selected"]]

if not ingredient_matcher.empty:
    ingredient_matcher["gc_amount"] = ingredient_matcher["size"].apply(lambda x: float(re.findall("\d+\.?\d*", x)[0]))
    ingredient_matcher["gc_unit"] = ingredient_matcher["size"].apply(lambda x: re.findall("[a-zA-Z]+", x)[0])
    ingredient_matcher["pack_amount"] = ingredient_matcher["gc_amount"] * ingredient_matcher["pack_size"]
    ingredient_matcher["pack_normed"] = ingredient_matcher["pack_amount"] * ingredient_matcher["gc_unit"].apply(lambda x: unit_conversions.get(x, 1)) * ingredient_matcher["order_quantity"]
    ingredient_matcher["line_total"] = ingredient_matcher["trade_price"] * ingredient_matcher["order_quantity"] * ingredient_matcher["pack_normed"]
    
    # we need to normalise this by the actual amount of food we need, rather
    # than the whole pack size
    ingredient_matcher["pounds_per_pack_normed"] = ingredient_matcher["pack_normed"] / ingredient_matcher["trade_price"]
    ingredient_matcher["required_amount_normed"] = ingredient_matcher["amount"] * ingredient_matcher["unit"].apply(lambda x: unit_conversions.get(x, 1))
    ingredient_matcher["pounds_per_required_amount_normed"] = ingredient_matcher["required_amount_normed"] / ingredient_matcher["trade_price"]
    
    ingredient_matcher["amount_excess"] = ingredient_matcher["pack_normed"] - ingredient_matcher["required_amount_normed"] 
    ingredient_matcher["enough_food"] = ingredient_matcher["amount_excess"] >= 0
    
    ingredient_matcher["price_rank"] = ingredient_matcher.groupby(["origin_index", "enough_food"])["line_total"].rank(method="min")
    ingredient_matcher["fraction_used"] = ingredient_matcher["required_amount_normed"] / ingredient_matcher["pack_normed"]
    ingredient_matcher["cost_fraction"] = ingredient_matcher["fraction_used"] * ingredient_matcher["trade_price"] * ingredient_matcher["order_quantity"]
    # ingredient_matcher["order_quantity"] = 1 # this will be the only value for now - need to create more rows with multiples
    ingredient_matcher["line_total"] = ingredient_matcher["order_quantity"] * ingredient_matcher["trade_price"]
    ingredient_matcher.loc[~ingredient_matcher["enough_food"], "price_rank"] = np.NaN

    ingredient_matcher.loc[ingredient_matcher["manually_selected"], "price_rank"] = 0

with col_right:
    st.text("Picked ingredients:")
    if debug:
        st.text("debug"); ingredient_matcher
        
    if not ingredient_matcher.empty:
        chosen_ingredients = (
            ingredient_matcher[ingredient_matcher["enough_food"]]
            .sort_values("price_rank")
            .groupby("origin_index")
            .head(1)
            .sort_values("origin_index")
            .reset_index(drop=True)
            # [["description", "pack_size", "size", "trade_price", "order_quantity", "line_total"]]
        )
    else:
        chosen_ingredients = pd.DataFrame(columns=["origin_index", "description", "pack_size", "size", "trade_price", "order_quantity", "line_total", "required_amount_normed", "fraction_used", "product_code"])
            
    # add in the fresh produce - under @
    chosen_ingredients = pd.concat([
        chosen_ingredients,
        pd.DataFrame([{
            "origin_index": row["origin_index"],
            "description": row["description"],
            "pack_size": np.NaN,
            "size": np.NaN,
            "trade_price": row["each_price_pounds"] if row["unit"] is None else row["price_per_kg"],
            "order_quantity": row["amount"] * unit_conversions.get(row["unit"], 1),
            "line_total": row["amount"] * row["each_price_pounds"] if row["unit"] is None else row["amount"] * unit_conversions.get(row["unit"], 1) * row["price_per_kg"],
            "cost_fraction": row["amount"] * row["each_price_pounds"] if row["unit"] is None else row["amount"] * unit_conversions.get(row["unit"], 1) * row["price_per_kg"],
        } for _, row in ingredient_matcher_manual.iterrows()])
    ])
    
    # in cases where an origin index has no adequate matching ingredients, we need to add
    # a placeholder row that says "ingredient not found"
    missing_indices = set(
        edited_df[
            (edited_df["ingredient"] != "") | 
            (edited_df["ingredient"].isnull()) | 
            (edited_df["manual_ingredient_selector"].notna())
        ].index
    ) - set(chosen_ingredients["origin_index"])
    
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
            
    chosen_ingredients[[
        "description", 
        "pack_size", 
        "size", 
        "trade_price", 
        "order_quantity", 
        "line_total", 
        "required_amount_normed", 
        "fraction_used", 
        "cost_fraction",
        "product_code",
    ]]
    
    if not chosen_ingredients.empty:
        st.text(
            f'Total cost:                           £{chosen_ingredients["line_total"].sum():.2f}\n'
            f'Cost of ingredients used:             £{chosen_ingredients["cost_fraction"].sum():.2f}\n'
            f'Cost of ingredients used per serving: £{chosen_ingredients["cost_fraction"].sum() / desired_recipe_servings:.2f} ({desired_recipe_servings} servings)\n'
        )
