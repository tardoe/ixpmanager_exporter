import requests, os, urllib.parse
from flask import Flask, request
app = Flask(__name__)

# FORMAT
# ixp_customer_port{instance="ixp.edgeix.net.au",customer="Customer Pty Ltd",asn="65001",target="pe1per1",interface="Ethernet1/1"} 1

IXP_MANAGER_HOST = os.environ.get("IXP_MANAGER_HOST")
IXP_MANAGER_API_KEY = os.environ.get("IXP_MANAGER_API_KEY")
EXPORTER_METRIC = "ixpmanager_customer"

def _get_ixp_manager_interfaces(target):
    url = urllib.parse.urljoin("https://" + IXP_MANAGER_HOST, "/api/v4/provisioner/layer2interfaces/switch-name/" + target + ".json")
    r = requests.get(url, headers={"X-IXP-Manager-API-Key" : IXP_MANAGER_API_KEY})

    if r.status_code != 200:
        return "IXP Manager returned a non-OK status code: " + r.status_code, 400
    
    prom_output = ""
    for interface in r.json()["layer2interfaces"]:
        for vlan in interface["vlans"]:
            if vlan["customVlanTag"] > 0:
                interface_name = interface["name"] + "." + str(vlan["customVlanTag"])
            else:
                interface_name = interface["name"]

            prom_output = prom_output + EXPORTER_METRIC + "{instance=\"" + IXP_MANAGER_HOST + "\",customer=\"" + interface["description"] + "\",asn=\"" + str(interface["asnum"]) + "\",target=\"" + target + "\",interface=\"" + interface_name + "\"} 1\n"

    return prom_output

@app.route('/metrics')
def handle_metrics_request():
    
    if IXP_MANAGER_HOST is None:
        return "IXP_MANAGER_HOST environment var not set.", 400

    if IXP_MANAGER_API_KEY is None:
        return "IXP_MANAGER_API_KEY environment var not set.", 400
    
    target = request.args.get('target')
    if target == None:
        return "Target required.", 400
    
    return _get_ixp_manager_interfaces(target)


if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0')
