import { control, latLng, map, marker } from 'leaflet'
import { getMarkerIcon } from './_leaflet.map.js'
import { Mapnik } from './_leaflet.osm.js'

const useMapContainer = document.querySelector('.diary-entry-use-map-container')
if (useMapContainer) {
    const latInput = useMapContainer.querySelector('input[name="latitude"]')
    const lonInput = useMapContainer.querySelector('input[name="longitude"]')
    const useMapBtn = useMapContainer.querySelector('.diary-entry-use-map-btn')
    const mapDiv = useMapContainer.querySelector('.leaflet-container')
    let map_ = undefined
    let marker_ = undefined

    // On map click, update the coordinates and move the marker
    const onMapClick = e => {
        latInput.value = e.latlng.lat
        lonInput.value = e.latlng.lng

        // If there's already a marker, move it, otherwise create a new one
        if (marker_)
            marker_.setLatLng(e.latlng)
        else
            marker_ = marker(e.latlng, { icon: getMarkerIcon() })
                .addTo(map_)
                .bindPopup(I18n.t('diary_entries.edit.marker_text'))
    }

    // On "Use Map" button click, show the map and hide the button
    useMapBtn.on('click', e => {
        useMapBtn.classList.add('d-none')
        mapDiv.classList.remove('d-none')

        const params = mapDiv.dataset
        const center = latLng(params.lat, params.lon)

        map_ = map(mapDiv, {
            attributionControl: false,
            zoomControl: false
        }).addLayer(new Mapnik())

        // Make zoom control respect RTL
        control.zoom({
            position: document.documentElement.dir === 'rtl' ? 'topleft' : 'topright'
        }).addTo(map_)

        // Display marker by default if there are coordinates
        if (latInput.value && lonInput.value)
            marker_ = marker(center, { icon: getMarkerIcon() })
                .addTo(map_)
                .bindPopup(I18n.t('diary_entries.edit.marker_text'))

        map_.setView(center, params.zoom)
        map_.on('click', onMapClick)
    })
}
