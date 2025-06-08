function initChart(containerSelector, chartData) {
  new InteractiveChart(containerSelector, chartData);
}

class InteractiveChart {
  constructor(containerId, data) {
    this.container = d3.select(containerId);
    this.data = data;
    this.width = 500;
    this.height = 500;
    this.radius = 200;
    this.center = { x: this.width / 2, y: this.height / 2 };
    this.initSVG();
    this.initZoom();
    this.draw();
    this.setupInteractions();
  }

  initSVG() {
    this.svg = this.container
      .select('#chart-wheel')
      .attr('width', this.width)
      .attr('height', this.height);
    this.g = this.svg.append('g');
    this.tooltip = this.container.select('#tooltip');
  }

  initZoom() {
    this.zoom = d3
      .zoom()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        this.g.attr('transform', event.transform);
      });
    this.svg.call(this.zoom);
    d3.select('#zoom-in').on('click', () => {
      this.svg.transition().call(this.zoom.scaleBy, 1.5);
    });
    d3.select('#zoom-out').on('click', () => {
      this.svg.transition().call(this.zoom.scaleBy, 1 / 1.5);
    });
    d3.select('#reset').on('click', () => {
      this.svg.transition().call(this.zoom.transform, d3.zoomIdentity);
    });
  }

  polarToCartesian(angle, radius) {
    const rad = ((angle - 90) * Math.PI) / 180;
    return {
      x: this.center.x + radius * Math.cos(rad),
      y: this.center.y + radius * Math.sin(rad),
    };
  }

  draw() {
    this.drawZodiacCircle();
    this.drawHouses();
    this.drawAspects();
    this.drawPlanets();
  }

  drawZodiacCircle() {
    this.g
      .append('circle')
      .attr('cx', this.center.x)
      .attr('cy', this.center.y)
      .attr('r', this.radius)
      .attr('fill', 'none')
      .attr('stroke', '#333')
      .attr('stroke-width', 2);
    const glyphs = ['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓'];
    glyphs.forEach((glyph, i) => {
      const angle = i * 30 + 15;
      const pos = this.polarToCartesian(angle, this.radius + 25);
      this.g
        .append('text')
        .attr('x', pos.x)
        .attr('y', pos.y)
        .attr('class', 'zodiac-glyph')
        .text(glyph);
    });
  }

  drawHouses() {
    this.data.cusps.forEach((cusp, i) => {
      const pos = this.polarToCartesian(cusp, this.radius);
      const isAngular = [0, 3, 6, 9].includes(i);
      this.g
        .append('line')
        .attr('x1', this.center.x)
        .attr('y1', this.center.y)
        .attr('x2', pos.x)
        .attr('y2', pos.y)
        .attr('class', `house-line ${isAngular ? 'angular' : ''}`);
      const nextCusp = this.data.cusps[(i + 1) % 12];
      const midAngle = (cusp + ((nextCusp - cusp + 360) % 360) / 2) % 360;
      const textPos = this.polarToCartesian(midAngle, this.radius * 0.6);
      this.g
        .append('text')
        .attr('x', textPos.x)
        .attr('y', textPos.y)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'central')
        .attr('font-size', '12px')
        .attr('fill', '#666')
        .text(i + 1);
    });
  }

  drawAspects() {
    const colors = {
      Conjunction: '#00ff00',
      Opposition: '#ff0000',
      Square: '#ff0000',
      Trine: '#00ff00',
      Sextile: '#0000ff',
    };
    this.data.aspects.forEach((asp) => {
      const pos1 = this.polarToCartesian(
        this.data.positions[asp.planet1],
        this.radius * 0.8,
      );
      const pos2 = this.polarToCartesian(
        this.data.positions[asp.planet2],
        this.radius * 0.8,
      );
      this.g
        .append('line')
        .attr('x1', pos1.x)
        .attr('y1', pos1.y)
        .attr('x2', pos2.x)
        .attr('y2', pos2.y)
        .attr('class', 'aspect-line')
        .attr('stroke', colors[asp.aspect] || '#999')
        .attr('stroke-width', asp.strength * 2)
        .attr('opacity', 0.6)
        .on('mouseover', (event) => {
          this.showTooltip(
            event,
            `${asp.planet1} ${asp.aspect} ${asp.planet2}<br/>Orb: ${asp.orb.toFixed(
              1,
            )}°`,
          );
        })
        .on('mouseout', () => this.hideTooltip());
    });
  }

  drawPlanets() {
    const groups = this.clusterPlanets();
    const glyphs = {
      Sun: '☉',
      Moon: '☽',
      Mercury: '☿',
      Venus: '♀',
      Mars: '♂',
      Jupiter: '♃',
      Saturn: '♄',
      Uranus: '♅',
      Neptune: '♆',
      Pluto: '♇',
    };
    groups.forEach((group) => {
      group.forEach((planet, i) => {
        const offset = (i - (group.length - 1) / 2) * 0.5;
        const angle = this.data.positions[planet] + offset;
        const pos = this.polarToCartesian(angle, this.radius * 0.85);
        this.g
          .append('circle')
          .attr('cx', pos.x)
          .attr('cy', pos.y)
          .attr('r', 5)
          .attr('class', 'planet-dot')
          .attr('fill', '#333')
          .on('mouseover', (event) => {
            const retro = this.data.retrogrades[planet] ? ' ℞' : '';
            this.showTooltip(
              event,
              `${planet}${retro}<br/>${this.formatLongitude(
                this.data.positions[planet],
              )}`,
            );
          })
          .on('mouseout', () => this.hideTooltip());
        this.g
          .append('text')
          .attr('x', pos.x)
          .attr('y', pos.y - 15)
          .attr('class', 'planet-glyph')
          .text(glyphs[planet] || planet[0]);
        if (this.data.retrogrades[planet]) {
          this.g
            .append('text')
            .attr('x', pos.x)
            .attr('y', pos.y + 15)
            .attr('class', 'planet-glyph')
            .attr('font-size', '10px')
            .text('℞');
        }
      });
    });
  }

  clusterPlanets() {
    const planets = Object.keys(this.data.positions);
    const groups = [];
    const used = new Set();
    planets.forEach((p) => {
      if (used.has(p)) return;
      const group = [p];
      used.add(p);
      planets.forEach((o) => {
        if (used.has(o)) return;
        const diff = Math.abs(this.data.positions[p] - this.data.positions[o]);
        const minDiff = Math.min(diff, 360 - diff);
        if (minDiff <= 3) {
          group.push(o);
          used.add(o);
        }
      });
      groups.push(group);
    });
    return groups;
  }

  formatLongitude(deg) {
    const signs = [
      'Aries',
      'Taurus',
      'Gemini',
      'Cancer',
      'Leo',
      'Virgo',
      'Libra',
      'Scorpio',
      'Sagittarius',
      'Capricorn',
      'Aquarius',
      'Pisces',
    ];
    const signIndex = Math.floor(deg / 30) % 12;
    const degInSign = deg % 30;
    const wholeDeg = Math.floor(degInSign);
    const minutes = Math.floor((degInSign - wholeDeg) * 60);
    return `${wholeDeg}° ${signs[signIndex]} ${minutes}'`;
  }

  showTooltip(event, content) {
    this.tooltip
      .style('opacity', 1)
      .html(content)
      .style('left', `${event.pageX + 10}px`)
      .style('top', `${event.pageY - 10}px`);
  }

  hideTooltip() {
    this.tooltip.style('opacity', 0);
  }

  setupInteractions() {
    this.g
      .selectAll('.aspect-line')
      .on('mouseover', function () {
        d3.select(this).attr('opacity', 1);
      })
      .on('mouseout', function () {
        d3.select(this).attr('opacity', 0.6);
      });
  }
}
