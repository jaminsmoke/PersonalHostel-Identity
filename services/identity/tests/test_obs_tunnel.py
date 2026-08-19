from scripts import obs_tunnel


def test_tunnels_mapping_known_services():
    assert obs_tunnel.TUNNELS == {
        "9090": "Prometheus",
        "9093": "Alertmanager",
        "3001": "Grafana",
    }


def test_default_ports_cubren_las_tres_uis():
    assert obs_tunnel.TUNNELS.keys() == set(["9090", "9093", "3001"])
    assert "9090" in obs_tunnel.TUNNELS
    assert "9093" in obs_tunnel.TUNNELS
    assert "3001" in obs_tunnel.TUNNELS


def test_forward_rechaza_puerto_no_numerico():
    assert obs_tunnel.forward_port(None, "abc") is False
