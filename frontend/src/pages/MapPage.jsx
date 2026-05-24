import { useState } from 'react'

export default function MapPage() {
  const [src] = useState(`/static/map.html?v=${Date.now()}`)
  return (
    <iframe
      className="map-frame"
      src={src}
      title="Carte live des véhicules"
    />
  )
}
