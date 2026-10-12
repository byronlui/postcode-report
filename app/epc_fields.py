"""Allowlisted certificate facts; do not expose arbitrary upstream fields."""
import re
GROUPS={
 '證書與物業': [('inspection_date','檢查日期',''),('tenure','業權（官方代碼）',''),('current_energy_efficiency','目前能源效率分數',''),('potential_energy_efficiency','潛在能源效率分數','')],
 'CO₂ 排放': [('co2_emissions_current','目前排放','tonnes/year'),('co2_emissions_potential','潛在排放','tonnes/year'),('co2_emiss_curr_per_floor_area','每平方米排放','kg/m²/year')],
 '能源消耗': [('energy_consumption_current','目前能源消耗','kWh/m²/year'),('energy_consumption_potential','潛在能源消耗','kWh/m²/year'),('energy_tariff','能源收費類型（官方代碼）',''),('mains_gas_flag','接駁天然氣',''),('photo_supply','太陽能光伏比例','%'),('wind_turbines_count','風力發電機數目',''),('extension_count','擴建部分數目','')],
 '地板': [('floor_description','地板描述',''),('floor_energy_eff','能源效率（官方代碼）',''),('floor_env_eff','環境效率（官方代碼）',''),('floor_level','樓層','')],
 '窗戶與玻璃': [('windows_description','窗戶描述',''),('glazed_type','玻璃類型（官方代碼）',''),('glazed_area','玻璃面積類別（官方代碼）',''),('multi_glaze_proportion','多層玻璃比例','%'),('windows_energy_eff','能源效率（官方代碼）',''),('windows_env_eff','環境效率（官方代碼）','')],
 '供暖與通風': [('heated_room_count','供暖房間數',''),('open_fireplaces_count','開放式壁爐數',''),('main_fuel_type','主要燃料（官方代碼）',''),('mainheat_description','主要供暖描述',''),('mainheatcont_description','供暖控制描述',''),('mainheat_energy_eff','供暖能源效率（官方代碼）',''),('mainheat_env_eff','供暖環境效率（官方代碼）',''),('secondheat_description','第二供暖系統',''),('mechanical_ventilation','機械通風（官方代碼）',''),('hotwater_description','熱水系統','')],
 '照明': [('lighting_description','照明描述',''),('lighting_cost_current','目前照明成本（證書估算）','£/year'),('lighting_cost_potential','潛在照明成本（證書估算）','£/year'),('lighting_energy_eff','能源效率（官方代碼）',''),('lighting_env_eff','環境效率（官方代碼）',''),('low_energy_fixed_light_count','低耗能固定燈具數',''),('low_energy_lighting','低耗能照明比例','%')],
 '屋頂與牆壁': [('roof_description','屋頂描述',''),('roof_energy_eff','屋頂能源效率（官方代碼）',''),('roof_env_eff','屋頂環境效率（官方代碼）',''),('walls_description','牆壁描述',''),('walls_energy_eff','牆壁能源效率（官方代碼）',''),('walls_env_eff','牆壁環境效率（官方代碼）','')]
}
ALIASES={'heated_room_count':['number_heated_rooms'],'open_fireplaces_count':['number_open_fireplaces'],'main_fuel_type':['main_fuel'],'mains_gas_flag':['mains_gas'],'wind_turbines_count':['wind_turbines'],'extension_count':['extensions'],'low_energy_fixed_light_count':['low_energy_fixed_lighting_outlets']}
ALIASES.update({'current_energy_efficiency':['energy_rating_current'],'potential_energy_efficiency':['energy_rating_potential'],'co2_emiss_curr_per_floor_area':['co2_emissions_current_per_floor_area'],'extension_count':['extensions','extensions_count'],'glazed_type':['multiple_glazing_type'],'multi_glaze_proportion':['multiple_glazed_proportion'],'low_energy_fixed_light_count':['low_energy_fixed_lighting_outlets','low_energy_fixed_lighting_outlets_count']})
def facts(root):
    norm=lambda s:re.sub('[^a-z0-9]','',s.lower())
    values={norm(k):v for k,v in root.items()}
    for k,v in root.get('sap_energy_source',{}).items():values.setdefault(norm(k),v)
    groups=[]
    for title,fields in GROUPS.items():
        rows=[]
        for key,label,unit in fields:
            v=next((values[norm(k)] for k in [key]+ALIASES.get(key,[]) if values.get(norm(k)) is not None),None)
            if isinstance(v,dict):v=v.get('value')
            if isinstance(v,(str,int,float)) and v!='':rows.append({'label':label,'value':v,'unit':unit})
        if rows:groups.append({'title':title,'rows':rows})
    for key,title in [('roofs','屋頂'),('walls','牆壁'),('floors','地板'),('window','窗戶'),('lighting','照明'),('hot_water','熱水'),('main_heating','主要供暖'),('main_heating_controls','供暖控制'),('secondary_heating','第二供暖系統')]:
        items=root.get(key,[])
        if isinstance(items,dict):items=[items]
        for i,item in enumerate(items if isinstance(items,list) else []):
            if not isinstance(item,dict):continue
            rows=[]
            for field,label in [('description','描述'),('energy_efficiency_rating','能源效率（官方代碼）'),('environmental_efficiency_rating','環境效率（官方代碼）')]:
                v=item.get(field)
                if isinstance(v,dict):v=v.get('value')
                if isinstance(v,(str,int,float)) and v!='':rows.append({'label':label,'value':v,'unit':''})
            if rows:groups.append({'title':title+(f' · 部分 {i+1}' if len(items)>1 else ''),'rows':rows})
    return groups
