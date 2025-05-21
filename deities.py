import textwrap
import pywikibot as pwb
import mwparserfromhell as mwp
import regex
import re
from pprint import pprint
from bs4 import BeautifulSoup as bs

ml_ci = regex.MULTILINE | regex.IGNORECASE
da_ci = regex.DOTALL | regex.IGNORECASE
ci = regex.IGNORECASE

def none_if(value, null_value=""):
    return None if value == null_value else value

# function to parse a value, parsing HTML, converting links to values, and extracting the arguments for templates
def parse_value(value, key_name):
    if value is not None:
        value = bs(value, 'html.parser').text
        if regex.match(r"^[^\[\{,\(]+$", value, flags=da_ci ):
            return none_if(value)
        test_val = regex.match(r"^\[\[([A-Za-z0-9 -',]+)\]\]$", value, flags=da_ci )
        if test_val is not None:
            return none_if(test_val.group(1))
        if regex.match(r"^\{\{[^\}]+\}\}$", value, da_ci):
            value = regex.match(r"^\{\{[^\}\/\|]+(?:\/|\|)([^\}]+)\}\}$", value, flags=da_ci ).group(1)
            return none_if(value)
        val_note = regex.search(r"''\(([^\)]+)\)''+", value, flags=da_ci )
        if val_note is not None:
            temp_val = regex.sub( regex.escape(val_note.group(0)), "", value, flags=da_ci )
            value = { 'value': temp_val, 'note': val_note.group(1) }

        val_type = type(value)
        test_val = value['value'] if val_type is dict else value
        val_ref = regex.findall(r"\{\{Ref\|([^\}\{}]+)\}\}", test_val, flags=da_ci )
        if len(val_ref) > 0:
            temp_val = regex.sub( r"\n", test_val, "", flags=da_ci ).strip()
            for ref in val_ref:
                temp_val = regex.sub( regex.escape("{{Ref|" + ref + "}}"), "", temp_val, flags=da_ci )
            ref_or_refs = ( val_ref[0] if len(val_ref) == 1 else [ref for ref in val_ref] )
            if val_type is dict:
                value['ref'] = ref_or_refs
            else:
                value = { 'value': temp_val, 'ref': ref_or_refs }

        val_type = type(value)
        test_val = value['value'] if val_type is dict else value  
        matches = regex.findall( r"(?:\[\[)(?<val>[^\]\|:<]+)\|?(?<alt>[^\]]+)?(?:\]\])", test_val, flags=da_ci  )
        if len(matches) > 0:
            if key_name == '2e-sanctification':
                if type(matches) is list and len(matches) == 1 and matches[0][1] == "":
                    value = matches[0][0] \
                        + ( "!" if regex.search(r"must", test_val, flags=ci ) else "?" )
                elif type(matches) is list and len(matches) == 2:
                    value = matches[0][0] \
                        + ( "!" if regex.search(r"must", test_val, flags=ci ) else "?" ) \
                            + matches[1][0] 
                elif val_type is dict:
                    value['value'] = test_val
                elif val_type is str:
                    value = test_val
                else:
                    value = False
                return none_if(value)
            
            if type(matches) is list:
                if any( [match[1] != "" for match in matches] ):
                    if val_type is str:
                        value = {}
                    value['value'] = [(match[0] if match[1] == "" else match[1]) for match in matches]
                    value['link'] = [(match[0] if match[1] != "" else None) for match in matches]
                else:
                    if val_type is dict:
                        value['value'] = [match[0] for match in matches] if len(matches) > 1 else matches[0][0]
                    else:
                        value = [match[0] for match in matches] if len(matches) > 1 else matches[0][0]

            val_type = type(value)
            if val_type is dict and hasattr(value,'link') and type(value['link']) is list:
                val_test = ["[[" + ( l + "|" + v if l is not None else v) + "]]" for v in value['value'] for l in value['link']]
            elif val_type is dict and hasattr(value,'link') and type(value['link']) is str:
                val_test = "[[" + ( value['link'] + "|" if hasattr(value,'link') else "" ) + value['value'] + "]]"
            else:
                val_test = [value] if type(value) is str else value
            copy = test_val
            for val in val_test:
                test_val = regex.sub( regex.escape(val), "", test_val, flags=da_ci  )
            esc_val = regex.sub( r"[^A-Za-z0-9 -]", "", test_val, flags=da_ci )
            if esc_val != "":
                if val_type is dict:
                    value['raw'] = copy
                else:
                    value = { 'value': value, 'raw': copy }        
        return none_if(value)

def split_and_parse(array, regexp, key, original_key=None, splits={}):
    if original_key is None:
        original_key = key
        splits = {}
    if len(splits.keys()) == 0:
        ra_split = array
    else:
        ra_split = splits[key]
    new_key = None
    for i in range(len(ra_split)):
        if regex.search(regexp, ra_split[i], flags=da_ci):
            new_key_and_first_val = regex.split(regexp, ra_split[i], flags=da_ci )
            new_key = original_key + '-' + regex.sub(r" ", "-", new_key_and_first_val[0].lower(), flags=da_ci )
            new_key = regex.sub(r"[^a-z0-9-]", "", new_key, flags=da_ci )
            splits[key] = ra_split[0:i-1]                
            splits[new_key] = [new_key_and_first_val[1]] + ra_split[i+1:]
            break
    if new_key in splits:
        return split_and_parse( splits[new_key], regexp, new_key, original_key, splits )
    elif len(splits.keys()) == 0:
        for i in range(len(array)):
            array[i] = parse_value(array[i], key)
        return array, None
    else:
        for k in splits:
            for i in range(len(splits[k])):
                splits[k][i] = parse_value(splits[k][i], k)
        return splits.pop(original_key), splits

def process_node(n, rebuild, dt_end, done=None, dt_start=None):
    str_form = ( None if hasattr(n, 'nodes') else n.value if hasattr(n, 'value') else str(n) ).strip("\n").strip()
    if str_form is None:
            n_count = len(n.nodes)
            while not done:
                n = n.nodes[i]
                rebuild, done = process_node(n, rebuild, dt_end, done, dt_start)
                i += 1
                if i == n_count:
                    break
            return rebuild, done
    elif done is None:
            str_start = regex.search( dt_start, str_form, flags=da_ci )
            if str_start is None:
                return None, None
            else:
                start_pos = str_start.pos
                str_end = regex.search( dt_end, str_form, flags=da_ci )
                if str_end is None:
                    return str_form[start_pos:], False
                else:
                    end_pos = str_end.start()
                    return str_form[start_pos:end_pos], True
    elif done == False:
        str_end = regex.search( dt_end, str_form, flags=da_ci )
        if str_end is None:
            rebuild += str_form
            return rebuild, False
        else:
            end_pos = str_end.start()
            rebuild += str_form[:end_pos]
            return rebuild, True
    else:
        return None, None

def rebuild_template(stripped_template, nodes, rebuild=None, child=False):
    dt = stripped_template
    tstr = str(dt).strip("\n").strip()
    
    _name = dt.name.lower().strip("\n").strip()
    dt_start = r"\{\{" + dt.name.strip("\n").strip()
    dt_end = r"\}\}\s*\n\s*\{\{(?:deity|interwiki\}\})"
    i = 0
    done = None
    while i < len(nodes):
        n = nodes[i]
        rebuild, done = process_node(n, rebuild, dt_end, done, dt_start)
        if done:
            break
        else:
            i += 1
    return rebuild, done
            

def repair_filter(template_name, wikicode,deity_name):
    t_name = template_name.lower().strip()
    deity_name = deity_name.lower().strip()

    first_try = wikicode.filter_templates(matches=lambda t: t.name.lower().strip("\n").strip().startswith(t_name))
    
    dnames = []
    if len(first_try) >= 1:
        match = None
        for dt in first_try:
            if dt.name.lower().strip("\n").strip() != deity_name:
                dnames.append(dt.name.lower().strip("\n").strip())
            elif dt.name.lower().strip("\n").strip() == deity_name:
                match = dt
        if match is not None:
            return match

    # second pass
    quick_and_dirty = mwp.parse(wikicode.strip_code()).filter_templates(matches=lambda t: t.name.lower().strip("\n").strip().startswith(t_name))
    if len(quick_and_dirty) == 0:
        raise KeyError("No " + t_name + " template found")
    elif len(quick_and_dirty) >= 1:
        for dt in quick_and_dirty:
            for param in dt.params:
                space_to_us = regex.sub(r" ", "_", param.name.strip("\n").strip().lower())
                clean_key = regex.sub(r"[^a-z0-9-_]", "", space_to_us)
                if clean_key == "name":
                    dname = param.value.lower().strip("\n").strip()
                    if dname not in dnames:
                        dnames.append( dname )
        if deity_name is not None:
            if deity_name not in dnames:
                raise KeyError("No template found for " + deity_name)
            else:
                dt = quick_and_dirty[dnames.index(deity_name)]
                dt_name = dt.name.lower().strip("\n").strip()
                nodes = mwp.parse(wikicode).nodes
                rebuild, done = rebuild_template(dt, nodes)
                rebuild = regex.sub(r"(\n?\|)(?=\s[A-Za-z0-9_ -]+=)", "♡\n|", rebuild, flags=da_ci)
                rebuild = regex.sub(r"(?<=♡\n\|\s[A-Za-z0-9_ -]+)(=\s?)", "=♤", rebuild, flags=da_ci)
                if done:
                    # wc_new = mwp.parse(rebuild)
                    new_params = []
                    param_num = len(dt.params)
                    for i in range(param_num):
                        param = dt.params[i]
                        param_name = param.name.strip().lower()
                        # next_name = r"" if i == param_num - 1 else dt.params[i+1].name.strip().lower()
                        param_re = regex.compile( "(?<=♡\n\| " + param_name + " +=♤)[^♡♤]+", flags=da_ci )
                        space_to_us = regex.sub(r" ", "_", param.name.strip("\n").strip().lower())
                        clean_key = regex.sub(r"[^a-z0-9-_]", "", space_to_us)
                        param_val = param_re.search( rebuild ).group(0) if param_re.search( rebuild ) is not None else ""
                        new_params.append(mwp.nodes.extras.parameter.Parameter(name=clean_key, value=param_val, showkey=True))
                    dt_new = mwp.wikicode.Template(name=dt_name, params=new_params)
                    return dt_new
                else:
                    raise KeyError("Template found for " + deity_name + " but could not be repaired")
        elif deity_name is None and len(quick_and_dirty) > 1:
            return [dt.name for dt in quick_and_dirty]
    




    #     elif dnum is not None:
    #         if dnum > len(quick_and_dirty):
    #             raise KeyError("Only found " + str(dnum) + " templates: " + ", ".join([dt.name for dt in quick_and_dirty]))
    #     elif deity_name is None and dnum is None and len(quick_and_dirty) > 1:
    #         return [dt.name for dt in quick_and_dirty]
    
    # try:
    #     output = node_recurse(t_name, mwp.parse(wikicode).nodes)
    #     if output is not None:
    #         if len(output) >= 1:
    #             if deity_name is not None:
    #                 for dt in output:
    #                     if dt.name.lower().strip("\n").strip() == deity_name:
    #                         return dt
    #                 if match_exists:
    #                     raise KeyError("Template found for " + deity_name + " but could not be repaired")
    #                 else:
    #                     raise KeyError("No template found for " + deity_name)
    #             elif dnum is not None:
    #                 if dnum <= len(output):
    #                     return output[dnum]
    #                 else:
    #                     raise KeyError("Only found " + str(dnum) + " templates: " + ", ".join([dt.name for dt in output]))
    #             elif deity_name is None and dnum is None and len(output) > 1:
    #                 return [dt.name for dt in output]
    #             elif len(output) == 1:
    #                 return output[0]
    #         elif len(output) == 0:
    #             raise KeyError("No " + t_name + " template found")
    #         else:
    #             raise KeyError("Unknown error")
    #     else:
    #         raise KeyError("No " + t_name + " template found")
    # except KeyError as e:
    #     print(e)
    #     return None
           
        
def get_deity(deity_name,site):
        deity_page = pwb.Page(site, deity_name)
        if deity_page.exists():
            deity_contents = deity_page.get()
            deity_wiki = mwp.parse(deity_contents)
            deity_template = None
            first_try = deity_wiki.filter_templates(matches=lambda t: t.name.lower().strip("\n").strip().startswith('deity'))
            if len(first_try) == 1 and type(first_try[0]) is mwp.nodes.template.Template:
                deity_template = first_try[0]
            elif len(first_try) > 1:
                raise ValueError("Multiple matching templates found")
            else:
                try:
                    deity_templates = repair_filter('deity', deity_wiki, deity_name)
                    if deity_templates is not None:
                        if type(deity_templates) is list and len(deity_templates) > 1:
                            raise ValueError("Multiple matching templates found")
                        elif type(deity_templates) is list and len(deity_templates) == 1:
                            deity_template = ( deity_templates[0] if type(deity_templates[0]) is mwp.nodes.template.Template else None )
                            if deity_template is None:
                                raise ValueError("Unknown error: " + str(deity_templates[0]))
                        elif type(deity_templates) is mwp.nodes.template.Template:
                            deity_template = deity_templates
                        else:
                            raise ValueError("Unknown error: " + str(deity_templates))
                except KeyError as e:
                    print(e)
                    return None
            

            # extract deity's Deity template properties, converting links to values, comma or newline or <br> separated lists to arrays, and only the arguments for templates
            deity = {}
            bonus_data = {}
            for param in deity_template.params:
                space_to_us = regex.sub(r" ", "_", param.name.strip().lower())
                clean_key = regex.sub(r"[^a-z0-9-_]", "", space_to_us)
                deity[clean_key] = param.value.strip()
            for key in deity:
                # replace ", " and "<br>" with "\n" to split on
                deity[key] = regex.split(r"(?:<br>)|(?:, ?)|(?:\n)", deity[key])
                if len(deity[key]) == 1:
                    deity[key] = parse_value( deity[key][0], key )
                elif len(deity[key]) > 1:
                    deity[key], new_bonus_data = split_and_parse(deity[key], r":\)?'' ?", key)
                    if new_bonus_data is not None:
                        for new_key in new_bonus_data:
                            bonus_data[new_key] = new_bonus_data[new_key]
            for key in bonus_data:
                deity[key] = bonus_data[key]
            review = []
            for key in deity:
                if type(deity[key]) is dict:
                    if 'raw' in deity[key]:
                        review.append( key )
                elif type(deity[key]) is list:
                    if any( [type(val) is dict and 'raw' in val for val in deity[key]] ):
                        review.append( key )
            if len(review) > 0:
                deity['review'] = review
            key_copy = [key for key in deity.keys()]
            for key in key_copy:
                if deity[key] is None:
                    deity.pop(key)
            return deity
        else:
            return None
    
def parse_deities(title, list=None, limit=None):
    site = pwb.Site(url='https://pathfinderwiki.com')
    page = pwb.Page(site, title)
    text = page.get()
    wc = mwp.parse(text)
    # convert wikicode to string
    wt = str(wc)

    templates = regex.finditer( r"(?:(?<=\| )([a-z_]+)(?: += *\n)((?:(?:\* \[\[)(?:[^\]]+)(?:\]\]s? *\n))+))", wt, flags=da_ci )

    deity_list = {}

    for t in templates:
        g = t.group(1)
        tds = [d.group(0) for d in regex.finditer( r"(?<=\* \[\[)[^\|\]]+", t.group(2), flags=da_ci ) if d.group(0) in list]
        for td in tds:
            if td in deity_list:
                deity_list[td].append(g)
            else:
                deity_list[td] = [g]
    
    deity_names = [key for key in deity_list.keys()]
    if limit is None:
        limit = len(deity_names)
    
    deities = {deity: get_deity(deity,site) for deity in deity_names[:limit]}
    return deities

deities = parse_deities('Template:Deities list', list=['Arazni'])

pprint(deities)
