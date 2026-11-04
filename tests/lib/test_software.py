from app.lib.software import SOFTWARE, filter_software


def test_software_filters():
    assert filter_software({}) == SOFTWARE
    assert [
        entry['name']
        for entry in filter_software({'platform': 'android', 'category': 'navigation'})
    ] == ['Organic Maps']
    assert len(filter_software({'license': 'open', 'status': 'active'})) == len(
        SOFTWARE
    )
    assert filter_software({'license': 'proprietary'}) == ()
    assert filter_software({'platform': 'ios', 'category': 'editing'}) == ()
    assert len({entry['name'] for entry in SOFTWARE}) == len(SOFTWARE)
