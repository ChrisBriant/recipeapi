from typing import List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random, os, dotenv, openai, re

app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

basedir = os.path.abspath(os.path.dirname(__file__))

dotenv_file = os.path.join(basedir, ".env")
if os.path.isfile(dotenv_file):
    dotenv.load_dotenv(dotenv_file)

#Load the open AI key
openai.api_key = os.getenv("OPENAI_API_KEY")

#Token limit
TOKEN_LIMIT = 800

#Models

class Card(BaseModel):
    cardnumber : int
    name: str

class Reading(BaseModel):
    cards :  List[Card] 
    message: str

class Key(BaseModel):
    key: str

class Recipe(BaseModel):
    possible: bool

class RecipeResponse(BaseModel):
    possible: bool
    title: str
    description: str
    ingredients: Dict[int, str]
    instructions: Dict[int, str]
    extra_ingredients: Dict[int, str]
    completion_tokens : int

class Ingredients(BaseModel):
    ingredient_list : List[str]


def get_reading_from_ai(cards):
    prompt = f'''The selected cards are {cards[0]['cardnumber']}:{cards[0]['name']},{cards[1]['cardnumber']}:{cards[1]['name']} and {cards[2]['cardnumber']}:{cards[2]['name']}. Give me a tarot reading based on these selected cards in 500 words or less'''
    try:
        response = openai.Completion.create(
            model="text-davinci-002",
            prompt=prompt,
            temperature=0.6,
            max_tokens=600,
        )
    except Exception as e:
        print(e)
        response = None
    return response

def get_cards_and_reading():
    selected_cards = []
    selected_card = random.sample(tarot_list,1)[0]
    selected_cards.append(selected_card)
    remaining_cards = [ card for card in tarot_list if card['cardnumber'] != selected_card['cardnumber']]
    selected_card = random.sample(remaining_cards,1)[0]
    remaining_cards = [ card for card in remaining_cards if card['cardnumber'] != selected_card['cardnumber']]
    selected_cards.append(selected_card)
    selected_card = random.sample(remaining_cards,1)[0]
    selected_cards.append(selected_card)
    reading = get_reading_from_ai(selected_cards)
    if reading:
        reading = reading.choices[0].text
    else:
        reading = 'Sorry I was unable to get a reading.'
    return {
        'cards' : selected_cards,
        'message' : reading
    }

#For handling errors where the token limit is not enough
class TokenLimitException(Exception):
    pass

#For handling errors when parsing the AI output
class ResponseParseException(Exception):
    pass


def get_enumerated_items_as_object(items_str):
       # use a regular expression to split the string based on the enumeration pattern
    items = re.findall(r"(\d+)\.\s*(\S.*?)\s*(?=\d+\.|$)", items_str)

    enumerated_items_dict = {}
    for item in items:
        # item is a tuple containing the number and ingredient
        number = int(item[0])
        #ingredient = item[1]
        # add the ingredient to the dictionary with the number as the key
        enumerated_items_dict[number] = item[1]
    return enumerated_items_dict

def get_recipe_from_ai(ingredients):
    response_obj = {}

    print(ingredients)
    prompt = 'I have the following ingredients:\n\n'
    for i in range(0,len(ingredients)):
        prompt += f'{i+1}. ' + ingredients[i] + '\n'
    prompt_posibility = prompt + '\n Is it possible to create a recipe? Please respond only with yes or no.'
    try:
        response = openai.Completion.create(
            model="text-davinci-002",
            prompt=prompt_posibility,
            temperature=0.6,
            max_tokens=600,
        )
    except Exception as e:
        print(e)
        response = None
    print(prompt) 
    print(response['choices'][0]['text'])
    #Check that the response contains "yes"
    pattern = re.compile(r"yes", re.IGNORECASE)
    if not pattern.search(response['choices'][0]['text']):
        #response_obj['possible'] = False
        response_obj = {
            'possible' : False,
            'title' : '',
            'description' : '',
            'ingredients' : {},
            'instructions' : {},
            'extra_ingredients' : {},
            'completion_tokens' : 0,
        }
        return response_obj
    #Get the recipe
    #response_obj['possible'] = True
    prompt_question = '''\nPlease suggest a recipe with these incredients. Format in the sections:\n
"Title" a title for the recipe\n
"Ingredients" which lists the ingredients (enumerated)\n
"Instructions" which describes how to make the recipe\n
"Extra Ingredients" which lists extra incredients that were not included in the prompt (enumerated)\n
"Description" a description of the recipe writen in an enticing manner\n'''
    prompt_recipe = prompt + prompt_question
    try:
        response = openai.Completion.create(
            model="text-davinci-002",
            prompt=prompt_recipe,
            temperature=0.6,
            max_tokens=TOKEN_LIMIT,
        )
        #print(response['usage']['completion_tokens'])
        print('Total tokens',response['usage']['total_tokens'])
        print('Token limit',TOKEN_LIMIT)
    except Exception as e:
        print(e)
        response = None
    if response['usage']['total_tokens'] > TOKEN_LIMIT:
        raise TokenLimitException('Not enough tokens to complete the request.')
    print('Here is a the response',response)
    try:
        response_str = response['choices'][0]['text']
        
        # Extract title
        title_match = re.search(r"Title:\s*(.*)", response_str)
        title = title_match.group(1)

        # Extract ingredients
        ingredients_match = re.search(r"Ingredients:\s*(.*)Instructions:", response_str, re.DOTALL)
        ingredients = ingredients_match.group(1)

        # Extract instructions
        instructions_match = re.search(r"Instructions:\s*(.*)Extra Ingredients:", response_str, re.DOTALL)
        instructions = instructions_match.group(1)

        # Extract description
        description_match = re.search(r"Description:\s*(.*)", response_str, re.DOTALL)
        description = description_match.group(1)


        # Extract extra ingredients
        extra_match = re.search(r"Extra Ingredients:\s*(.*)", response_str, re.DOTALL)
        extra = extra_match.group(1)
    except Exception:
        raise ResponseParseException('Unable to process the AI output')

    # print("Title:", title)
    # print("Ingredients:", ingredients)
    # print("Instructions:", instructions)
    # print("Extra Ingredients:", extra)

    ingredient_dict = get_enumerated_items_as_object(ingredients)
    print(ingredient_dict)
    instruction_dict = get_enumerated_items_as_object(instructions)
    print(instruction_dict)
    extra_ingredient_dict = get_enumerated_items_as_object(extra)
    print(extra_ingredient_dict)
    print(description)
    response_obj = {
        'possible' : True,
        'title' : title,
        'description' : description,
        'ingredients' : ingredient_dict,
        'instructions' : instruction_dict,
        'extra_ingredients' : extra_ingredient_dict,
        'completion_tokens' : response['usage']['total_tokens'] 
     }
    return response_obj


@app.post("/recipe/",response_model=RecipeResponse)
def get_recipe(key: Key, ingredients:Ingredients):
    auth_key = os.getenv("AUTH_KEY")
    if not key.key == auth_key:
        raise HTTPException(status_code=403, detail="Unauthorised")
    try:
        recipe = get_recipe_from_ai(ingredients.ingredient_list)
    except TokenLimitException:
        raise HTTPException(status_code=400, detail="Token limit exceeded")
    except ResponseParseException:
        raise HTTPException(status_code=400, detail="Unable to prcess the reponse received")
    #recipe = {'possible' : False}
    return recipe
