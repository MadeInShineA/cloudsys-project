#import "@preview/cetz:0.5.2": canvas, draw

#set text(
  font: "Source Sans Pro"
)
#set page(
  width: auto,
  height: auto,
  margin: 0.5cm
)

#let colors = (
  physical: green.lighten(70%),
  docker: blue.lighten(70%),
  aws: orange.lighten(70%)
)

#let component(pos, body, fill: none, name: none, ..args) = draw.content(
  pos,
  body,
  frame: "rect",
  fill: fill,
  name: name,
  ..args.named()
)

#let arrow(start, end, name) = {
  draw.line(start, end, name: name)
  draw.mark(
    name + ".mid",
    name + ".end",
    symbol: ">",
    fill: black,
    anchor: "center"
  )
}

#let zone(name, body, label) = {
  draw.group(name: name, body, padding: 10pt)

  draw.rect(
    name + ".north-west",
    name + ".south-east",
    stroke: 1pt,
    radius: 5pt
  )

  draw.content(
    name + ".north",
    strong(label),
    anchor: "south"
  )
}

#let machines(n, target, label, fill: none) = {
  let delta-a = 20deg
  let start-a = 180deg - (n - 1) * delta-a / 2
  for i in range(n) {
    let anchor = (
      "south-",
      "",
      "north-",
    ).at(i) + "east"
    component(
      (
        rel: (start-a + delta-a * i, 2),
        to: target
      ),
      anchor: anchor,
      fill: fill,
      name: "machine-" + str(i),
      label,
    )
    
    arrow(
      "machine-" + str(i),
      target,
      "uart-" + str(i)
    )
  }
}

#let legend() = {
  let swatch(col) = box(
    fill: col,
    stroke: col.darken(40%),
    width: 10pt,
    height: 10pt,
    radius: 4pt
  )
  let legend = grid(
    columns: 2,
    align: (x, _) => if x == 0 {center} else {left} + horizon,
    column-gutter: 4pt,
    row-gutter: 6pt,
    swatch(colors.physical), [Physical device],
    swatch(colors.docker), [Docker container],
    swatch(colors.aws), [AWS Service],
  )
  draw.group(
    {
      draw.content(
        (
          rel: (-1, -0.3),
          to: "client.north-west",
        ),
        anchor: "north-east",
        name: "table",
        legend
      )
      draw.content(
        (
          rel: (-0.2, 0),
          to: "table.north-west"
        ),
        anchor: "south-west",
        padding: 0pt,
        text(fill: gray.darken(70%))[_*Legend*_]
      )
    },
    name: "legend",
    padding: 5pt,
  )
  draw.rect(
    "legend.north-west",
    "legend.south-east",
    stroke: gray.darken(20%),
    radius: 4pt,
    
  )
}

#let architecture(simulated: false) = canvas({
  draw.set-style(
    content: (
      padding: 5pt,
    )
  )

  zone(
    "edge",
    {
      component(
        (0, 0),
        fill: colors.docker,
        name: "collector"
      )[Collector]

      if simulated {
        machines(3, "collector.west", fill: colors.docker)[Simulator]
      }
    },
  )[Edge device]

  if not simulated {
    machines(3, "edge.collector.west", fill: colors.physical)[Machine]
  }

  zone(
    "cloud",
    {
      component(
        (
          rel: (2, 0),
          to: "edge.east",
        ),
        anchor: "west",
        fill: colors.aws,
        name: "mqtt",
        align(center)[
          MQTT Broker\
          #text(size: 0.7em)[_(AWS IoT Core)_]
        ]
      )
      component(
        (
          rel: (0, -1.5),
          to: "mqtt.south"
        ),
        anchor: "north",
        fill: colors.aws,
        name: "dashboard",
        align(center)[
          Dashboard\
          #text(size: 0.7em)[_(Grafana)_]
        ],
      )
      component(
        (
          rel: (2, 0),
          to: ("mqtt.south", 50%, "dashboard.north")
        ),
        anchor: "west",
        fill: colors.aws,
        name: "db",
        align(center)[
          Database\
          #text(size: 0.7em)[_(DynamoDB)_]
        ],
      )

      arrow("mqtt", "db", "l-mqtt-db")
      arrow("db", "dashboard", "l-db-dashboard")
    },
  )[Cloud services (AWS)]

  arrow(
    "edge.collector.east",
    "cloud.mqtt.west",
    "l-collector-mqtt",
  )

  component(
    (rel: (-2, 0), to: "cloud.dashboard.west"),
    anchor: "east",
    name: "client",
  )[Engineer]

  let pt(base, side, offset) = (
    base + "." + side,
    offset,
    base + ".north-" + side,
  )
  let d = 0.1
  arrow(
    pt("cloud.dashboard", "west", d),
    pt("client", "east", d),
    "l-dashboard-client"
  )
  arrow(
    pt("client", "east", -d),
    pt("cloud.dashboard", "west", -d),
    "l-client-dashboard"
  )

  legend()
})

#align(center, text(size: 1.5em)[*Physical devices*])
#architecture(simulated: false)
#pagebreak()
#align(center, text(size: 1.5em)[*Simulated*])
#architecture(simulated: true)
