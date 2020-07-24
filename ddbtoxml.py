#!/usr/local/bin/python3
import os
import sys
import json
import math
import uuid
import requests
import tempfile
import shutil
import re
import base64
import argparse
import xml.etree.cElementTree as ET

from json import JSONDecodeError
from slugify import slugify

def getJSON(theurl):
        rawjson = ""
        urlm = re.match(r'(http[s]?://)?((www\.)?dndbeyond.com|ddb.ac)/(profile/[^/]*/)?character[s]?/([0-9]*)(/.*)?',theurl)
        if urlm:
                #Pretend to be firefox
                user_agent = "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:70.0) Gecko/20100101 Firefox/70.0"
                headers = {'User-Agent': user_agent}
                #urlcomponents = theurl.split("/")
                #charid = urlcomponents[-1]
                #if charid == "json":
                #        charid = urlcomponents[-2]
                charid = urlm.group(5)
                url = "https://www.dndbeyond.com/character/{}/json".format(charid)
                response = requests.get(url,headers=headers)
                if response.status_code != 200:
                        print (theurl)
                        print ("Could not download this character from D&D Beyond: {}".format(response.status_code))
                        print ("Make sure the character is public")
                        print(charid)
                        return
                else:
                        if "character" in response.json():
                                character = response.json()["character"]
                        else:
                                character = response.json()
                        infusions_resp = requests.get("https://character-service.dndbeyond.com/characters/v2/infusions?characterId=" + str(character['id']),headers=headers)
                        if infusions_resp.status_code == 200:
                                character['infusions'] = infusions_resp.json()
                        else:
                                print(infusions_resp)
                        return character
        else:
                print ("This is not a url for D&D Beyond: {}".format(theurl))
                return

def genXML(character,compendium):       
        level = 0
        player = ET.SubElement(compendium, 'player', { 'id': str(uuid.uuid5(uuid.NAMESPACE_URL,character['readonlyUrl'])) } )
        name = ET.SubElement(player, 'name')
        name.text = "{}".format(character["name"])
        slug = ET.SubElement(player, 'slug')
        slug.text = "{}".format(slugify(character["name"]))
        ddb = ET.SubElement(player, 'ddb')
        ddb.text = "{}".format(character["id"])
        cclass = ET.SubElement(player, 'class')
        if len(character["classes"]) > 1:
                allclasses = []
                for acclass in character["classes"]:
                        level += acclass["level"]
                        allclasses.append("{} {}".format(acclass["definition"]["name"],acclass["level"]))
                        cclass.text = '/'.join(allclasses)
        else:
                characterclass = character["classes"][0]["definition"]["name"]
                level = character["classes"][0]["level"]
                cclass.text = "{} {}".format(characterclass,level)
        if character["alignmentId"]:
                if character["alignmentId"] == 1:
                        cclass.text += ", Lawful Good"
                if character["alignmentId"] == 2:
                        cclass.text += ", Neutral Good"
                if character["alignmentId"] == 3:
                        cclass.text += ", Chaotic Good"
                if character["alignmentId"] == 4:
                        cclass.text += ", Lawful Neutral"
                if character["alignmentId"] == 5:
                        cclass.text += ", Neutral"
                if character["alignmentId"] == 6:
                        cclass.text += ", Chaotic Neutral"
                if character["alignmentId"] == 7:
                        cclass.text += ", Lawful Evil"
                if character["alignmentId"] == 8:
                        cclass.text += ", Neutral Evil"
                if character["alignmentId"] == 9:
                        cclass.text += ", Chaotic Evil"
        agegen = []
        if character["age"]:
                agegen.append("{}".format(character["age"]))
        if character["gender"]:
                agegen.append("{}".format(character["gender"]))
        if len(agegen) > 0:
                cclass.text += " ({})".format(", ".join(agegen))
        clevel = ET.SubElement(player, 'level')
        clevel.text = "{}".format(level)
        xp = ET.SubElement(player, 'xp')
        xp.text = "{}".format(character["currentXp"])
        hitpoints = character["baseHitPoints"]
        armorclass = 0
        basearmor = 10
        hasarmor = None
        stat_str = character["stats"][0]["value"]
        stat_dex = character["stats"][1]["value"]
        stat_con = character["stats"][2]["value"]
        stat_int = character["stats"][3]["value"]
        stat_wis = character["stats"][4]["value"]
        stat_cha = character["stats"][5]["value"]
        race = character["race"]["fullName"]
        speed = character["race"]["weightSpeeds"]["normal"]["walk"]
        modifiers = character["modifiers"]
        senses = []
        for modifier in (modifiers["race"]+modifiers["class"]+modifiers["background"]+modifiers["item"]+modifiers["feat"]+modifiers["condition"]):
                skip_modifier = False
                for inv_item in character["inventory"]:
                    if modifier["componentId"] == inv_item["definition"]["id"] and "grantedModifiers" in inv_item["definition"]:
                        if inv_item["definition"]["canEquip"] and not inv_item["equipped"]:
                            for grantedMod in inv_item["definition"]["grantedModifiers"]:
                                if modifier["id"] == grantedMod["id"]:
                                    skip_modifier = True
                        else:
                            skip_modifier = False
                if skip_modifier:
                        continue
                if modifier["type"].lower() == "bonus":
                        if modifier["subType"].lower() == "strength-score" and modifier["value"]:
                                stat_str += modifier["value"]
                        if modifier["subType"].lower() == "dexterity-score" and modifier["value"]:
                                stat_dex += modifier["value"]
                        if modifier["subType"].lower() == "constitution-score" and modifier["value"]:
                                stat_con += modifier["value"]
                        if modifier["subType"].lower() == "intelligence-score" and modifier["value"]:
                                stat_int += modifier["value"]
                        if modifier["subType"].lower() == "wisdom-score" and modifier["value"]:
                                stat_wis += modifier["value"]
                        if modifier["subType"].lower() == "charisma-score" and modifier["value"]:
                                stat_cha += modifier["value"]
                        if modifier["subType"].lower() == "hit-points-per-level" and modifier["value"]:
                                hitpoints += modifier["value"]*level
                        if modifier["subType"].lower() == "armor-class" and modifier["value"]:
                                armorclass += modifier["value"]
                if modifier["type"].lower() == "set":
                        if modifier["subType"].lower() == "minimum-base-armor" and modifier["value"]:
                                basearmor = modifier["value"]
        if character["bonusStats"][0]["value"]:
                stat_str += character["bonusStats"][0]["value"]
        if character["bonusStats"][1]["value"]:
                stat_dex += character["bonusStats"][1]["value"]
        if character["bonusStats"][2]["value"]:
                stat_con += character["bonusStats"][2]["value"]
        if character["bonusStats"][3]["value"]:
                stat_int += character["bonusStats"][3]["value"]
        if character["bonusStats"][4]["value"]:
                stat_wis += character["bonusStats"][4]["value"]
        if character["bonusStats"][5]["value"]:
                stat_cha += character["bonusStats"][5]["value"]

        if character["overrideStats"][0]["value"]:
                stat_str = character["overrideStats"][0]["value"]
        if character["overrideStats"][1]["value"]:
                stat_dex = character["overrideStats"][1]["value"]
        if character["overrideStats"][2]["value"]:
                stat_con = character["overrideStats"][2]["value"]
        if character["overrideStats"][3]["value"]:
                stat_int = character["overrideStats"][3]["value"]
        if character["overrideStats"][4]["value"]:
                stat_wis = character["overrideStats"][4]["value"]
        if character["overrideStats"][5]["value"]:
                stat_cha = character["overrideStats"][5]["value"]
        hitpoints += math.floor((stat_con - 10)/2)*level
        if character["overrideHitPoints"]:
                hitpoints = character["overrideHitPoints"]
        initiative = math.floor((stat_dex - 10)/2)
        equipment = []
        for equip in character["inventory"]:
#               for i in range(equip["quantity"]):
#                       equipment.append(equip["definition"]["name"])
#               if equip["quantity"] > 1:
#                       equipment.append("{} (x{:d})".format(equip["definition"]["name"],equip["quantity"]))
#               else:
#                       equipment.append(equip["definition"]["name"])
                equipname = equip["definition"]["name"]
                if equipname == "Ball Bearings (bag of 1,000)":
                        equipname = "Ball Bearings"
                if ', ' in equipname:
                        equipparts = equipname.split(', ',1)
                        if equipparts[1].startswith('+'):
                                if equipparts[0].lower().endswith("leather") or equipparts[0].lower().endswith("padded") or equipparts[0].lower().endswith("plate") or equipparts[0].lower().endswith("hide"):
                                        equipparts[0] += " Armor"
                                equipname = equipparts[0] + " " + equipparts[1]
                        else:
                                if equipparts[1].endswith(" (50 feet)"):
                                        equipname = equipparts[1][:-10] + " " + equipparts[0] + " (50 feet)"
                                else:
                                        equipname = equipparts[1] + " " + equipparts[0]
                m = re.search(r'Potion of Healing \((.*?)\)',equipname)
                if m:
                        equipname = "Potion of {} Healing".format(m.group(1))
                equipname = re.sub(r'(Arrow|Bolt|Needle|Bullet)s(.*)(?<!\([0-9]{2}\))$',r'\1\2',equipname)
                if "armor" in equip["definition"]["type"].lower():
                        if equipname.lower().endswith("leather") or equipname.lower().endswith("padded") or equipname.lower().endswith("plate") or equipname.lower().endswith("hide"):
                                equipment.append(equipname + " Armor")
                        else:
                                equipment.append(equipname)
                else:
                        equipment.append(equipname)
                if equip["equipped"] == True and "armorClass" in equip["definition"]:
                        if "Armor" in equip["definition"]["type"]:
                                hasarmor = equip["definition"]["type"]
                        armorclass += equip["definition"]["armorClass"]
                        if 'infusions' in character:
                                for infusion in character["infusions"]:
                                        if infusion["inventoryMappingId"] == equip["id"] and infusion["choiceKey"] == "364B2EAD-4019-4953-A0FF-7B59AE1021EE":
                                                armorclass += 1
        if not hasarmor:
                acAddStr = False
                acAddCon = False
                acAddInt = False
                acAddWis = False
                acAddCha = False
                armorclass += basearmor
                armorclass += math.floor((stat_dex - 10)/2)
        elif hasarmor.lower() == "medium armor" and math.floor((stat_dex - 10)/2) > 2:
                armorclass += 2
        elif hasarmor.lower() != "heavy armor":
                armorclass += math.floor((stat_dex - 10)/2)
        light = ""
        languages = []
        resistence = []
        immunity = []
        skill = {}
        str_save = math.floor((stat_str - 10)/2)
        skill["Athletics"] = str_save
        dex_save = math.floor((stat_dex - 10)/2)
        skill["Acrobatics"] = dex_save
        skill["Sleight of Hand"] = dex_save
        skill["Stealth"] = dex_save
        con_save = math.floor((stat_con - 10)/2)
        int_save = math.floor((stat_int - 10)/2)
        skill["Arcana"] = int_save
        skill["History"] = int_save
        skill["Investigation"] = int_save
        skill["Nature"] = int_save
        skill["Religion"] = int_save
        wis_save = math.floor((stat_wis - 10)/2)
        skill["Animal Handling"] = wis_save
        skill["Insight"] = wis_save
        skill["Medicine"] = wis_save
        skill["Perception"] = wis_save
        skill["Survival"] = wis_save
        cha_save = math.floor((stat_cha - 10)/2)
        skill["Deception"] = cha_save
        skill["Intimidation"] = cha_save
        skill["Performance"] = cha_save
        skill["Persuasion"] = cha_save
        light = ET.SubElement(player, 'light', {"id": str(uuid.uuid5(uuid.NAMESPACE_URL,character['readonlyUrl'] + "/light" )) } )
        enabled = ET.SubElement(light, 'enabled')
        enabled.text = "YES"
        radiusmin = ET.SubElement(light, 'radiusMin')
        radiusmin.text = "1"
        radiusmax = ET.SubElement(light, 'radiusMax')
        radiusmax.text = "0"
        color = ET.SubElement(light, 'color')
        color.text = "#ffffff"
        opacity = ET.SubElement(light, 'opacity')
        opacity.text = "0.5"
        visible = ET.SubElement(light, 'alwaysVisible')
        visible.text = "YES"

        for modifier in (modifiers["race"]+modifiers["class"]+modifiers["background"]+modifiers["item"]+modifiers["feat"]+modifiers["condition"]):
                skip_modifier = False
                for inv_item in character["inventory"]:
                    if modifier["componentId"] == inv_item["definition"]["id"] and "grantedModifiers" in inv_item["definition"]:
                        if inv_item["definition"]["canEquip"] and not inv_item["equipped"]:
                            for grantedMod in inv_item["definition"]["grantedModifiers"]:
                                if modifier["id"] == grantedMod["id"]:
                                    skip_modifier = True
                        else:
                            skip_modifier = False
                if skip_modifier:
                    continue
                if modifier["type"].lower() == "half-proficiency":
                        bonus = math.floor(math.ceil(((level/4)+1))/2)
                        if modifier["subType"].lower() == "athletics" or modifier["subType"].lower() == "ability-checks":
                                skill["Athletics"] = math.floor((stat_str - 10)/2) + bonus
                        if modifier["subType"].lower() == "acrobatics" or modifier["subType"].lower() == "ability-checks":
                                skill["Acrobatics"] = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "sleight-of-hand" or modifier["subType"].lower() == "ability-checks":
                                skill["Sleight of Hand"] = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "stealth" or modifier["subType"].lower() == "ability-checks":
                                skill["Stealth"] = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "arcana" or modifier["subType"].lower() == "ability-checks":
                                skill["Arcana"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "history" or modifier["subType"].lower() == "ability-checks":
                                skill["History"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "investigation" or modifier["subType"].lower() == "ability-checks":
                                skill["Investigation"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "nature" or modifier["subType"].lower() == "ability-checks":
                                skill["Nature"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "religion" or modifier["subType"].lower() == "ability-checks":
                                skill["Religion"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "animal-handling" or modifier["subType"].lower() == "ability-checks":
                                skill["Animal Handling"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "insight" or modifier["subType"].lower() == "ability-checks":
                                skill["Insight"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "medicine" or modifier["subType"].lower() == "ability-checks":
                                skill["Medicine"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "perception" or modifier["subType"].lower() == "ability-checks":
                                skill["Perception"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "survival" or modifier["subType"].lower() == "ability-checks":
                                skill["Survival"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "deception" or modifier["subType"].lower() == "ability-checks":
                                skill["Deception"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "intimidation" or modifier["subType"].lower() == "ability-checks":
                                skill["Intimidation"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "performance" or modifier["subType"].lower() == "ability-checks":
                                skill["Performance"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "persuasion" or modifier["subType"].lower() == "ability-checks":
                                skill["Persuasion"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "initiative":
                                initiative = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "strength-saving-throws":
                                str_save = math.floor((stat_str - 10)/2) + bonus
                        if modifier["subType"].lower() == "dexterity-saving-throws":
                                dex_save = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "constitution-saving-throws":
                                con_save = math.floor((stat_con - 10)/2) + bonus
                        if modifier["subType"].lower() == "intelligence-saving-throws":
                                int_save = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "wisdom-saving-throws":
                                wis_save = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "charisma-saving-throws":
                                cha_save = math.floor((stat_cha - 10)/2) + bonus
        for modifier in (modifiers["race"]+modifiers["class"]+modifiers["background"]+modifiers["item"]+modifiers["feat"]+modifiers["condition"]):
                skip_modifier = False
                for inv_item in character["inventory"]:
                    if modifier["componentId"] == inv_item["definition"]["id"] and "grantedModifiers" in inv_item["definition"]:
                        if inv_item["definition"]["canEquip"] and not inv_item["equipped"]:
                            for grantedMod in inv_item["definition"]["grantedModifiers"]:
                                if modifier["id"] == grantedMod["id"]:
                                    skip_modifier = True
                        else:
                            skip_modifier = False
                if skip_modifier:
                    continue
                if modifier["type"].lower() == "proficiency":
                        bonus = math.ceil((level/4)+1)
                        if modifier["subType"].lower() == "athletics" or modifier["subType"].lower() == "ability-checks":
                                skill["Athletics"] = math.floor((stat_str - 10)/2) + bonus
                        if modifier["subType"].lower() == "acrobatics" or modifier["subType"].lower() == "ability-checks":
                                skill["Acrobatics"] = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "sleight-of-hand" or modifier["subType"].lower() == "ability-checks":
                                skill["Sleight of Hand"] = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "stealth" or modifier["subType"].lower() == "ability-checks":
                                skill["Stealth"] = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "arcana" or modifier["subType"].lower() == "ability-checks":
                                skill["Arcana"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "history" or modifier["subType"].lower() == "ability-checks":
                                skill["History"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "investigation" or modifier["subType"].lower() == "ability-checks":
                                skill["Investigation"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "nature" or modifier["subType"].lower() == "ability-checks":
                                skill["Nature"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "religion" or modifier["subType"].lower() == "ability-checks":
                                skill["Religion"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "animal-handling" or modifier["subType"].lower() == "ability-checks":
                                skill["Animal Handling"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "insight" or modifier["subType"].lower() == "ability-checks":
                                skill["Insight"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "medicine" or modifier["subType"].lower() == "ability-checks":
                                skill["Medicine"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "perception" or modifier["subType"].lower() == "ability-checks":
                                skill["Perception"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "survival" or modifier["subType"].lower() == "ability-checks":
                                skill["Survival"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "deception" or modifier["subType"].lower() == "ability-checks":
                                skill["Deception"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "intimidation" or modifier["subType"].lower() == "ability-checks":
                                skill["Intimidation"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "performance" or modifier["subType"].lower() == "ability-checks":
                                skill["Performance"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "persuasion" or modifier["subType"].lower() == "ability-checks":
                                skill["Persuasion"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "initiative":
                                initiative = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "strength-saving-throws":
                                str_save = math.floor((stat_str - 10)/2) + bonus
                        if modifier["subType"].lower() == "dexterity-saving-throws":
                                dex_save = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "constitution-saving-throws":
                                con_save = math.floor((stat_con - 10)/2) + bonus
                        if modifier["subType"].lower() == "intelligence-saving-throws":
                                int_save = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "wisdom-saving-throws":
                                wis_save = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "charisma-saving-throws":
                                cha_save = math.floor((stat_cha - 10)/2) + bonus
        for modifier in (modifiers["race"]+modifiers["class"]+modifiers["background"]+modifiers["item"]+modifiers["feat"]+modifiers["condition"]):
                skip_modifier = False
                for inv_item in character["inventory"]:
                    if modifier["componentId"] == inv_item["definition"]["id"] and "grantedModifiers" in inv_item["definition"]:
                        if inv_item["definition"]["canEquip"] and not inv_item["equipped"]:
                            for grantedMod in inv_item["definition"]["grantedModifiers"]:
                                if modifier["id"] == grantedMod["id"]:
                                    skip_modifier = True
                        else:
                            skip_modifier = False
                if skip_modifier:
                    continue
                if modifier["type"].lower() == "expertise":
                        bonus = (math.ceil((level/4)+1)*2)
                        if modifier["subType"].lower() == "athletics" or modifier["subType"].lower() == "ability-checks":
                                skill["Athletics"] = math.floor((stat_str - 10)/2) + bonus
                        if modifier["subType"].lower() == "acrobatics" or modifier["subType"].lower() == "ability-checks":
                                skill["Acrobatics"] = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "sleight-of-hand" or modifier["subType"].lower() == "ability-checks":
                                skill["Sleight of Hand"] = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "stealth" or modifier["subType"].lower() == "ability-checks":
                                skill["Stealth"] = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "arcana" or modifier["subType"].lower() == "ability-checks":
                                skill["Arcana"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "history" or modifier["subType"].lower() == "ability-checks":
                                skill["History"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "investigation" or modifier["subType"].lower() == "ability-checks":
                                skill["Investigation"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "nature" or modifier["subType"].lower() == "ability-checks":
                                skill["Nature"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "religion" or modifier["subType"].lower() == "ability-checks":
                                skill["Religion"] = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "animal-handling" or modifier["subType"].lower() == "ability-checks":
                                skill["Animal Handling"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "insight" or modifier["subType"].lower() == "ability-checks":
                                skill["Insight"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "medicine" or modifier["subType"].lower() == "ability-checks":
                                skill["Medicine"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "perception" or modifier["subType"].lower() == "ability-checks":
                                skill["Perception"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "survival" or modifier["subType"].lower() == "ability-checks":
                                skill["Survival"] = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "deception" or modifier["subType"].lower() == "ability-checks":
                                skill["Deception"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "intimidation" or modifier["subType"].lower() == "ability-checks":
                                skill["Intimidation"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "performance" or modifier["subType"].lower() == "ability-checks":
                                skill["Performance"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "persuasion" or modifier["subType"].lower() == "ability-checks":
                                skill["Persuasion"] = math.floor((stat_cha - 10)/2) + bonus
                        if modifier["subType"].lower() == "initiative":
                                initiative = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "strength-saving-throws":
                                str_save = math.floor((stat_str - 10)/2) + bonus
                        if modifier["subType"].lower() == "dexterity-saving-throws":
                                dex_save = math.floor((stat_dex - 10)/2) + bonus
                        if modifier["subType"].lower() == "constitution-saving-throws":
                                con_save = math.floor((stat_con - 10)/2) + bonus
                        if modifier["subType"].lower() == "intelligence-saving-throws":
                                int_save = math.floor((stat_int - 10)/2) + bonus
                        if modifier["subType"].lower() == "wisdom-saving-throws":
                                wis_save = math.floor((stat_wis - 10)/2) + bonus
                        if modifier["subType"].lower() == "charisma-saving-throws":
                                cha_save = math.floor((stat_cha - 10)/2) + bonus
        for modifier in (modifiers["race"]+modifiers["class"]+modifiers["background"]+modifiers["item"]+modifiers["feat"]+modifiers["condition"]):
                skip_modifier = False
                for inv_item in character["inventory"]:
                    if modifier["componentId"] == inv_item["definition"]["id"] and "grantedModifiers" in inv_item["definition"]:
                        if inv_item["definition"]["canEquip"] and not inv_item["equipped"]:
                            for grantedMod in inv_item["definition"]["grantedModifiers"]:
                                if modifier["id"] == grantedMod["id"]:
                                    skip_modifier = True
                        else:
                            skip_modifier = False
                if skip_modifier:
                    continue
                if modifier["type"].lower() == "set" and modifier["subType"].lower() == "unarmored-armor-class" and not hasarmor:
                        if modifier["statId"] == 1 and not acAddStr:
                                acAddStr = True
                                armorclass += math.floor((stat_str - 10)/2)
                        if modifier["statId"] == 3 and not acAddCon:
                                acAddCon = True
                                armorclass += math.floor((stat_con - 10)/2)
                        if modifier["statId"] == 4 and not acAddInt:
                                acAddInt = True
                                armorclass += math.floor((stat_int - 10)/2)
                        if modifier["statId"] == 5 and not acAddWis:
                                acAddWis = True
                                armorclass += math.floor((stat_wis - 10)/2)
                        if modifier["statId"] == 6 and not acAddCha:
                                acAddCha = True
                                armorclass += math.floor((stat_cha - 10)/2)
                        if modifier["value"] is not None:
                                armorclass += modifier["value"]
                if modifier["type"].lower() == "ignore" and modifier["subType"].lower() == "unarmored-dex-ac-bonus" and not hasarmor:
                        armorclass -= math.floor((stat_dex - 10)/2)
                if (modifier["type"].lower() == "set-base" or modifier["type"].lower() == "sense") and modifier["subType"].lower() == "darkvision":
                        senses.append("{} {} ft.".format(modifier["subType"].lower(),modifier["value"]))
                        radiusmin.text = "0"
                        radiusmax.text = str(modifier["value"])
                if modifier["type"].lower() == "language":
                        languages.append(modifier["friendlySubtypeName"])
                if modifier["type"].lower() == "resistance":
                        resistence.append(modifier["friendlySubtypeName"])
                if modifier["type"].lower() == "immunity":
                        immunity.append(modifier["friendlySubtypeName"])
        spells = []
        for spell in character["spells"]["race"]:
                spells.append(spell["definition"]["name"])
        for spell in character["spells"]["class"]:
                spells.append(spell["definition"]["name"])
        for spell in character["spells"]["item"]:
                spells.append(spell["definition"]["name"])
        for spell in character["spells"]["feat"]:
                spells.append(spell["definition"]["name"])
        for classsp in character["classSpells"]:
                for spell in classsp["spells"]:
                        spells.append(spell["definition"]["name"])
        party = ""
        if "campaign" in character and character["campaign"] is not None:
                party = character["campaign"]["name"]
                campaign = ET.SubElement(player, 'campaign', { "ref": "/campaign/" + slugify(character["campaign"]["name"]) })
                #campaign.text = "{}".format(party)
        features = []
        background = ""
        def rmTags(m):
                if m.group(1) == "&nbsp;":
                        return " "
                elif m.group(1).startswith("\n\n"):
                        return "\n"
                else:
                        return ""
        if "background" in character and character["background"] is not None and character["background"]["definition"] is not None:
                background = character["background"]["definition"]["name"]
                bg_def = character["background"]["definition"]
                features.append( { "isbg": bg_def['name'], "name": bg_def['featureName'], "text": re.sub(r'((</?(dl|dt|p|div).*?>)+|\&nbsp;|\n[\n]+)',rmTags,bg_def['featureDescription']).strip() } )
        feats = []
        for feat in character["feats"]:
                feats.append(feat["definition"]["name"])
                feat_def = feat["definition"]
                feat_text = re.sub(r'((</?(dl|dt|p|div).*?>)+|\&nbsp;|\n[\n]+)',rmTags,feat_def['snippet'])
                if 'feat' in character['options']:
                        for ft_opt in character['options']['feat']:
                                if ft_opt['componentId'] == feat_def['id']:
                                        feat_text += "\n • <i>{}</i> {}".format(ft_opt['definition']['name'],re.sub(r'((</?(dl|dt|p|div).*?>)+|\&nbsp;|\n[\n]+)',rmTags,ft_opt['definition']['snippet']) )
                features.append( { "name": feat_def['name'], "text": feat_text } )
        personality = character["traits"]["personalityTraits"]
        bonds = character["traits"]["bonds"]
        ideals = character["traits"]["ideals"]
        flaws = character["traits"]["flaws"]
        appearance = character["traits"]["appearance"]
        racec = ET.SubElement(player, 'race')
        racec.text = "{}".format(race)
        initiativec = ET.SubElement(player, 'initiative')
        initiativec.text = "{}".format(initiative)
        ac = ET.SubElement(player, 'ac')
        ac.text = "{}".format(armorclass)
        hp = ET.SubElement(player, 'hp')
        hp.text = "{}".format(hitpoints)
        speedc = ET.SubElement(player, 'speed')
        speedc.text = "{}".format(speed)
        strs = ET.SubElement(player, 'str')
        strs.text = "{}".format(stat_str)
        dex = ET.SubElement(player, 'dex')
        dex.text = "{}".format(stat_dex)
        con = ET.SubElement(player, 'con')
        con.text = "{}".format(stat_con)
        ints = ET.SubElement(player, 'int')
        ints.text = "{}".format(stat_int)
        wis = ET.SubElement(player, 'wis')
        wis.text = "{}".format(stat_wis)
        cha = ET.SubElement(player, 'cha')
        cha.text = "{}".format(stat_cha)
        partyc = ET.SubElement(player, 'party')
        partyc.text = "{}".format(party)
        faction = ET.SubElement(player, 'faction')
        faction.text = "{}".format("")
        passive = ET.SubElement(player, 'passive')
        passive.text = "{}".format(skill["Perception"]+10)
        spellsc = ET.SubElement(player, 'spells')
        spellsc.text = ", ".join(spells)
        sensesc = ET.SubElement(player, 'senses')
        sensesc.text = ", ".join(senses)
        languagesc = ET.SubElement(player, 'languages')
        languagesc.text = ", ".join(languages)
        equipmentc = ET.SubElement(player, 'equipment')
        equipmentc.text = ", ".join(equipment)
        if character["avatarUrl"] != "":
                image = ET.SubElement(player, 'image')
                image.text = character["avatarUrl"].split('/')[-1]
        personalityc = ET.SubElement(player, 'personality')
        personalityc.text = "{}".format(personality)
        idealsc = ET.SubElement(player, 'ideals')
        idealsc.text = "{}".format(ideals)
        bondsc = ET.SubElement(player, 'bonds')
        bondsc.text = "{}".format(bonds)
        flawsc = ET.SubElement(player, 'flaws')
        flawsc.text = "{}".format(flaws)
        skills = []
        for sk in sorted(skill.keys()):
                skills.append("{} {:+d}".format(sk,skill[sk]))
        skill = ET.SubElement(player, 'skill')
        skill.text = "{}".format(", ".join(skills))

        save = ET.SubElement(player, 'save')
        save.text = "Str {:+d}, Dex {:+d}, Con {:+d}, Int {:+d}, Wis {:+d}, Cha {:+d}".format(str_save,dex_save,con_save,int_save,wis_save,cha_save)
        resist = ET.SubElement(player, 'resist')
        resist.text = ", ".join(resistence)
        immune = ET.SubElement(player, 'immune')
        immune.text = ", ".join(immunity)
        backgroundc = ET.SubElement(player, 'background')
        backgroundc.text = "{}".format(background)
        featsc = ET.SubElement(player, 'feats')
        featsc.text = ", ".join(feats)
        descr = ET.SubElement(player, 'descr')
        descr.text = ""
        hasfeats = False
        for feature in features:
                if 'isbg' in feature:
                        descr.text += "<b>Background: {}</b>\n".format(feature['isbg'])
                elif not hasfeats:
                        hasfeats = True
                        descr.text += "<b>Feats</b>\n"
                def replDDBTag(m):
                        modifier = -100
                        if m.group(2) or m.group(3):
                                stats = m.group(2) if m.group(2) else m.group(3)
                                for stat in stats.split(','):
                                        if stat.strip() == "str":
                                                mod = math.floor((stat_str - 10)/2)
                                        elif stat.strip() == "dex":
                                                mod = math.floor((stat_dex - 10)/2)
                                        elif stat.strip() == "con":
                                                mod = math.floor((stat_con - 10)/2)
                                        elif stat.strip() == "int":
                                                mod = math.floor((stat_int - 10)/2)
                                        elif stat.strip() == "wis":
                                                mod = math.floor((stat_wis - 10)/2)
                                        elif stat.strip() == "cha":
                                                mod = math.floor((stat_cha - 10)/2)
                                        if mod > modifier:
                                                modifier = mod
                        if modifier == -100:
                                modifier = 0
                        if m.group(1).startswith("characterlevel+modifier:"):
                                return str(level+modifier) if level+modifier >0 else "0"
                        elif m.group(1).startswith("savedc:"):
                                modifier += math.ceil((level/4)+1)
                                return str(8+modifier) if 8+modifier >0 else "0"
                        elif m.group(1) == "proficiency":
                                return str(math.ceil((level/4)+1))

                descr.text += "<i>{}</i> {}\n".format(feature["name"],re.sub(r'{{(proficiency|characterlevel\+modifier:(.*?)#.*|savedc:(.*?))}}',replDDBTag,feature["text"]))
        for (key,value) in character['notes'].items():
                if value:
                        if not descr.text.endswith("\n"):
                                descr.text += "\n"
                        title = key.title()
                        if key.lower() == "personalpossessions":
                                title = "Other Posessions"
                        elif key.lower() == "othernotes":
                                title = "Other Notes"
                        elif key.lower() == "otherholdinga":
                                title = "Other Holdings"
                        descr.text += "<b>{}</b>\n{}\n".format(title,re.sub(r'\&nbsp;'," ",value.strip()))
        if character['faith']:
                descr.text += "<b>Faith:</b> {}\n".format(re.sub(r'\&nbsp;'," ",character['faith']))
        if appearance or character['eyes'] or character['hair'] or character['skin'] or character['height'] or character['weight']:
                descr.text += "<b>Appearance</b>\n"
                if character['eyes']:
                        descr.text += "<i>Eyes:</i> {}\n".format(character['eyes'])
                if character['hair']:
                        descr.text += "<i>Hair:</i> {}\n".format(character['hair'])
                if character['skin']:
                        descr.text += "<i>Skin:</i> {}\n".format(character['skin'])
                if character['height']:
                        descr.text += "<i>Height:</i> {}\n".format(character['height'])
                if character['weight']:
                        descr.text += "<i>Weight:</i> {}\n".format(character['weight'])
                if appearance:
                        descr.text += "{}\n".format(appearance)
        descr.text += "\n\n<i><a href=\"https://www.dndbeyond.com/characters/{}\">Imported from D&D Beyond</a></i>".format(character["id"])
        return

def findURLS(fp):
        fp.seek(0, 0)
        characters = []
        regex = re.compile("<a[^>]*href=\"(/profile/.*/[0-9]+)\"[^>]*class=\"ddb-campaigns-character-card-header-upper-details-link\"[^>]*>")
        for line in fp:
                m = regex.search(line)
                if m:
                        characterurl = m.group(1)
                        if not characterurl.startswith("https://www.dndbeyond.com/"):
                                characters.append("https://www.dndbeyond.com"+characterurl)
                        else:
                                characters.append(characterurl)
        return characters

def main():
        parser = argparse.ArgumentParser(
        description="Converts D&D Beyond characters to an Encounter+ compendium file")
        parser.add_argument('characterurls', nargs="*", type=str, help="D&D Beyond Character URL or JSON file")
        parser.add_argument('--campaign',dest="campaign",action='store', default=None, nargs=1,help="Load all characters that share a campaign with this one (takes a URL or a JSON file)")
        parser.add_argument('--campaign-file',dest="campaignfile",action='store', default=None, nargs=1,help="Load all characters that are found in a campaign html file")
        args = parser.parse_args()      

        tempdir = tempfile.mkdtemp(prefix="ddbtoxml_")
        comependiumxml = os.path.join(tempdir, "compendium.xml")
        playersdir = os.path.join(tempdir, "players")
        os.mkdir(playersdir)
        #with open(comependiumxml,mode='a',encoding='utf-8') as comependium:
        #       comependium.write("<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"no\"?>\n<compendium>\n")
        compendium = ET.Element('compendium')
        if args.campaign:
                if os.path.isfile(args.campaign[0]):
                        with open(args.campaign[0],"r") as jsonfile:
                                charjson = json.loads(jsonfile.read())
                                jsonfile.close()
                else:
                        charjson = getJSON(args.campaign[0])
                if "character" in charjson:
                        character = charjson["character"]
                else:
                        character = charjson
                if "campaign" not in character or character["campaign"] is None:
                        print("This character is not a member of a campaign.")
                else:
                        for ch in character["campaign"]["characters"]:
                                if ch['privacyType'] == 3:
                                        args.characterurls.append("https://www.dndbeyond.com/character/{}/json".format(ch['characterId']))
        if args.campaignfile:
                regex = re.compile("<a[^>]*href=\"(/profile/.*/[0-9]+)\"[^>]*class=\"ddb-campaigns-character-card-header-upper-details-link\"[^>]*>")
                try:
                        readin = open(args.campaignfile[0],'r')
                        args = [sys.argv[0]]
                        for line in readin:
                                m = regex.search(line)
                                if m:
                                        characterurl = m.group(1)
                                        if not characterurl.startswith("https://www.dndbeyond.com/"):
                                                args.characterurls.append("https://www.dndbeyond.com"+characterurl)
                                        else:
                                                args.characterurls.append(characterurl)
                                readin.close()
                except:
                        pass
        characters = []
        for character in args.characterurls:
                if os.path.isfile(character):
                                with open(character) as infile:
                                        try:
                                                json.load(infile)
                                                characters.append(character)
                                        except JSONDecodeError:
                                                found = findURLS(infile)
                                                characters.extend(found)
                else:
                        characters.append(character)
        for acharacter in characters:
                if os.path.isfile(acharacter):
                        if os.path.isfile(acharacter):
                                with open(acharacter,"r") as jsonfile:
                                        charjson = json.loads(jsonfile.read())
                        else:
                                charjson = json.loads(sys.stdin.read())
                        if "character" in charjson:
                                character = charjson["character"]
                        else:
                                character = charjson
                else:
                        character = getJSON(acharacter)
                if character is not None:
                        genXML(character,compendium)
                        #with open(comependiumxml,mode='a',encoding='utf-8') as comependium:
                        #       comependium.write(xmloutput)
                        if character["avatarUrl"] != "":
                                local_filename = os.path.join(playersdir,character["avatarUrl"].split('/')[-1])
                                r = requests.get(character["avatarUrl"], stream=True)
                                if r.status_code == 200:
                                        with open(local_filename, 'wb') as f:
                                                for chunk in r.iter_content(chunk_size=8192):
                                                        f.write(chunk)
        #with open(comependiumxml,mode='a',encoding='utf-8') as comependium:
        #       comependium.write("</compendium>")

        def _prettyFormat(elem, level=0):
                """
                @summary: Formats ElementTree element so that it prints pretty (recursive)
                @param elem: ElementTree element to be pretty formatted
                @param level: How many levels deep to indent for
                @todo: May need to add an encoding parameter
                """
                tab = "    "

                i = "\n" + level*tab
                if len(elem):
                        if not elem.text or not elem.text.strip():
                                elem.text = i + tab
                        for e in elem:
                                _prettyFormat(e, level+1)
                                if not e.tail or not e.tail.strip():
                                        e.tail = i + tab
                        if not e.tail or not e.tail.strip():
                                e.tail = i
                        else:
                                if level and (not elem.tail or not elem.tail.strip()):
                                        elem.tail = i
        _prettyFormat(compendium)
        tree = ET.ElementTree(compendium)
        tree.write(comependiumxml,xml_declaration=True, short_empty_elements=False,encoding='utf-8')


        zipfile = shutil.make_archive("ddbxml","zip",tempdir)
        os.rename(zipfile,os.path.join(os.getcwd(),"ddbxml.compendium"))
        zipfile = os.path.join(os.getcwd(),"ddbxml.compendium")
        try:
                import console
                console.open_in (zipfile)
        except ImportError:
                print(zipfile)

        try:
                shutil.rmtree(tempdir)
        except:
                print("Warning: error trying to delete the temporal directory:", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)

if __name__== "__main__":
        main()
