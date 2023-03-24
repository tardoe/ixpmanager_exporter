import requests, os, urllib.parse, argparse
from flask import Flask, request

app = Flask(__name__)

# FORMAT
# ixp_customer_port{instance="ixp.edgeix.net.au",customer="Customer Pty Ltd",asn="65001",target="pe1per1",interface="Ethernet1/1", parent_interface_name="Ethernet1/1", subinterface_index="0"} 1
# ixp_customer_port{instance="ixp.edgeix.net.au",customer="Customer Pty Ltd",asn="65001",target="pe1per1",interface="Ethernet1/1.100", parent_interface_name="Ethernet1/1", subinterface_index="100"} 1


###
# Regular customer: layer2interface: name = Ethernet1/1
# Reseller customer: layer2interface: name = Ethernet1/2
# Extended reach customer: >1 VLAN on a given port, name = Ethernet1/1
#

IXP_MANAGER_HOST = os.environ.get("IXP_MANAGER_HOST")
IXP_MANAGER_API_KEY = os.environ.get("IXP_MANAGER_API_KEY")
EXPORTER_METRIC = "ixpmanager_customer"

EXPORTER_PORTS_METRIC = "ixpmanager_ports"
EXPORTER_SVCS_METRIC = "ixpmanager_svcs_peering"


def _get_ixp_manager_interfaces(target):
    url = urllib.parse.urljoin(
        "https://" + IXP_MANAGER_HOST,
        "/api/v4/provisioner/layer2interfaces/switch-name/" + target + ".json",
    )
    r = requests.get(url, headers={"X-IXP-Manager-API-Key": IXP_MANAGER_API_KEY})

    #print(r.json()["layer2interfaces"][0])

    if r.status_code != 200:
        return "IXP Manager returned a non-OK status code: " + r.status_code, 400
    
    # ixpmanager_ports
    ## Physical ports and their associated customer.
    ## Assumption: physical ports don't have a sub-interface.
    ##             physical ports include ethernet bundles / port-channels

    prom_output = ""

    # build a LAG map, key: interface, value: lagmaster interface name (e.g. PortChannel10)
    lags = {}
    for interface in r.json()["layer2interfaces"]:
        if interface.get("lagmaster"):
            for i in interface["lagmembers"]:
                lags[i] = interface["name"]


    for interface in r.json()["layer2interfaces"]:
        # mark if interfaces are an LACP Bundle or not.
        bundle = "true" if interface.get("lagmaster") else "false"

        # mark if interface is a member or not
        member = "true" if not interface.get("lagmaster") and interface.get("lagframing") else "false"

        if "." not in interface["name"]:
            # no sub-interfaces here
            if lags.get(interface["name"]):
                bundle_parent = '",bundle_parent="' + lags.get(interface["name"]) + '"'
            else:
                bundle_parent = ''

            prom_output = (
                prom_output 
                + EXPORTER_PORTS_METRIC
                + ' {instance="'
                + IXP_MANAGER_HOST
                + '",customer="'
                + interface["description"]
                + '",asn="'
                + str(interface["asnum"])
                + '",target="'
                + target
                # interface_name is used by openconfig, 
                # we need this to match here so we can join this to 
                # IXP-M data with the openconfig data in Prom.
                + '",interface_name="' 
                + interface["name"]
                + '",bundle="'
                + bundle
                + '",member="'
                + member
                + bundle_parent #optional based on bundle
                + '} 1\n'
            )
    
    for interface in r.json()["layer2interfaces"]:
        # only collate services listed on LAG Masters or non-LAG interfaces to avoid duplication
        if interface.get("lagmaster") or interface["lagframing"] == False:
            # mark if interfaces are an LACP Bundle or not.
            bundle = "true" if interface.get("lagmaster") else "false"

            for vlan in interface["vlans"]:
                infra_vlan = vlan["number"]
                subinterface_index = str(vlan["customVlanTag"])
                parent_interface = interface["name"].split(".")[0] # incase the dot-syntax is included in IXP-M
                svc_interface = parent_interface + "." + subinterface_index


                prom_output = (
                    prom_output
                    + EXPORTER_SVCS_METRIC
                    + ' {instance="'
                    + IXP_MANAGER_HOST
                    + '",customer="'
                    + interface["description"]
                    + '",asn="'
                    + str(interface["asnum"])
                    + '",target="'
                    + target
                    # interface_name in openconfig_subinterfaces is the physical / LAG interface name
                    # E.g. Ethernet1/2 or PortChannel40
                    + '",interface_name="'
                    + parent_interface
                    # we need the interface subindex so we can match it onto openconfig_subinterfaces
                    + '",subinterface_index="'
                    + str(subinterface_index)
                    # useful label to have
                    + '",svc_interface="'
                    + svc_interface
                    + '",bundle="'
                    + bundle
                    + '",peering_vlan="'
                    + str(infra_vlan)
                    + '"} 1\n'
                )

    return prom_output


@app.route("/metrics")
def handle_metrics_request():

    if IXP_MANAGER_HOST is None:
        return "IXP_MANAGER_HOST environment var not set.", 400

    if IXP_MANAGER_API_KEY is None:
        return "IXP_MANAGER_API_KEY environment var not set.", 400

    target = request.args.get("target")
    if target == None:
        return "Target required.", 400

    return _get_ixp_manager_interfaces(target)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
