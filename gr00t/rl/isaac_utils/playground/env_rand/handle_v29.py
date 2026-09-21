"""B05 geometry in metres; NumPy/SciPy construction is independent of Kit.

Sections are transported using the fixed door normal, including S inflections.
Convex sweep cells share end planes; only the axle/root intersections overlap.
Mass moments integrate these polyhedra and subtract those intersections once.
"""
import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation


FAMILIES = tuple(f"F{i}" for i in range(7))
_LENGTH = dict(F0=.125, F1=.130, F2=.130, F3=.135, F4=.130, F5=.140, F6=.130, X1=.135)


def _curve(family, q):
    """Planar centreline and derivative, q in [0,1], before lambda scaling."""
    q = np.asarray(q)
    length = _LENGTH[family]
    x, z = length*q, np.zeros_like(q)
    dx, dz = np.full_like(q, length), np.zeros_like(q)
    if family in ("F3", "X1"):
        angle = (q-.5)*length/.4
        x = .4*(np.sin(angle)+np.sin(length/.8))
        z = .4*(np.cos(angle)-np.cos(length/.8))
        dx, dz = length*np.cos(angle), -length*np.sin(angle)
    elif family == "F4":
        z = .003*np.sin(2*np.pi*q)
        dz = .006*np.pi*np.cos(2*np.pi*q)
    elif family == "F5":
        # Piecewise polynomial is the design, not a clipped invalid input.
        left, right = x < .032, x > .108
        v = np.where(left, x/.032, np.where(right, (.140-x)/.032, 1.))
        z = .008*v*v*(3-2*v)
        dz = np.where(left, 1., np.where(right, -1., 0.))*.008*6*v*(1-v)*length/.032
    return np.stack((x, z), axis=-1), np.stack((dx, dz), axis=-1)


def _arc(family, q):
    if family not in ("F4", "F5"):
        return _LENGTH[family]*q
    return quad(lambda t: float(np.linalg.norm(_curve(family, t)[1])), 0., q,
                epsabs=1.e-11, points=([.032/.140, .108/.140] if family == "F5" and q == 1. else None))[0]


def _free_interval(family):
    if family in ("F0", "F6"):
        return np.array([.030, .095 if family == "F0" else .100])
    if family in ("F1", "F2"):
        return np.array([.028, .102])
    if family in ("F3", "X1"):
        return np.array([.033, .102])
    if family == "F4":
        return np.array([.031, _arc(family, 1.)-.031])
    return np.array([_arc(family, .034/.140), _arc(family, .106/.140)])


def sample_handle_parameters(family=None, nominal=False, rng=None):
    """Sample one fixed door; X1 is available only as an explicit nominal asset."""
    rng = np.random if rng is None else rng
    family = str(rng.choice(FAMILIES)) if family is None else family
    if family not in FAMILIES and not (family == "X1" and nominal):
        raise ValueError(f"Unsupported training handle family {family!r}")
    noncircular = family in ("F1", "F2", "X1")
    scale = 1. if nominal else float(rng.uniform(max(.9, .065/np.diff(_free_interval(family))[0]), 1.1))
    k = 1. if nominal else float(rng.uniform(.85, 1.1))
    diameter = (.024 if family == "F4" else .026) if nominal else float(rng.uniform(.021, .028) if family == "F6" else rng.uniform(.019, .030))
    normal, closing = ((.030*k, .018*k) if family == "F2" else (.028*k, .020*k)) if noncircular else (diameter, diameter)
    p = dict(version=29, family=family, plane_scale=scale,
             face_standoff_m=.0775 if nominal else float(rng.uniform(.055, .085)),
             neck_radius_m=.013 if nominal else float(rng.uniform(.011, .015)),
             section_kind="rounded_rectangle" if family == "F2" else "ellipse" if noncircular else "circle",
             section_normal_diameter_m=normal, section_closing_diameter_m=closing,
             corner_radius_m=.006*k if family == "F2" else 0.,
             section_roll_rad=0. if nominal or not noncircular else float(rng.uniform(-np.pi/2, np.pi/2)),
             return_present=False if nominal else bool(rng.random() < .5))
    a, b, r = normal/2, closing/2, p["corner_radius_m"]
    p["tip_cap_extension_m"] = float(np.hypot(a-r, b-r)+r if family == "F2" else max(a, b)-(.001 if family == "F6" else 0.))
    if p["return_present"]:
        ceiling = min(.060, p["face_standoff_m"]-p["tip_cap_extension_m"]-.008)
        radius = float(rng.uniform(.020, min(.030, ceiling)))
        p.update(return_radius_m=radius, return_depth_m=float(rng.uniform(radius, ceiling)))
    else:
        p.update(return_radius_m=0., return_depth_m=0.)
    return p


def _section(p, q):
    a, b = p["section_normal_diameter_m"]/2, p["section_closing_diameter_m"]/2
    if p["family"] == "F6":
        a = b = a+.001-.002*q*q*(3-2*q)
    angles = np.arange(32)*2*np.pi/32
    if p["section_kind"] == "rounded_rectangle":
        r = p["corner_radius_m"]
        # Six angular subdivisions per rounded corner; straight faces connect them.
        angles = np.concatenate([np.linspace(i*np.pi/2, (i+1)*np.pi/2, 7) for i in range(4)])
        quadrant = np.repeat(np.arange(4), 7)
        sn = np.where((quadrant == 0) | (quadrant == 3), 1., -1.)
        sc = np.where(quadrant < 2, 1., -1.)
        section = np.c_[sn*(a-r)+r*np.cos(angles), sc*(b-r)+r*np.sin(angles)]
    else:
        section = np.c_[a*np.cos(angles), b*np.sin(angles)]
    phi = p["section_roll_rad"]
    return section @ np.array([[np.cos(phi), np.sin(phi)], [-np.sin(phi), np.cos(phi)]])


def _hull(points):
    return ConvexHull(np.asarray(points, dtype=np.float64))


def _polygon_count(hull):
    # Qhull returns triangles. PhysX limits coplanar merged convex polygons.
    return len(np.unique(np.round(hull.equations, 10), axis=0))


def _bisect_hull(hull, axis):
    """Partition at an axis-aligned plane using exact edge-plane intersections."""
    points = hull.points
    cut = (points[hull.vertices, axis].min()+points[hull.vertices, axis].max())/2
    distance = points[:, axis]-cut
    edges = np.unique(np.sort(np.concatenate((hull.simplices[:, [0, 1]],
                        hull.simplices[:, [1, 2]], hull.simplices[:, [2, 0]])), axis=1), axis=0)
    crossing = edges[distance[edges[:, 0]]*distance[edges[:, 1]] < 0.]
    weight = distance[crossing[:, 0]]/(distance[crossing[:, 0]]-distance[crossing[:, 1]])
    intersections = points[crossing[:, 0]]+weight[:, None]*(points[crossing[:, 1]]-points[crossing[:, 0]])
    intersections[:, axis] = cut
    return tuple(_hull(np.vstack((points[mask], intersections)))
                 for mask in (distance <= 0., distance >= 0.))


def _gpu_convex_parts(hull):
    """Preserve the original polyhedron while meeting both GPU convex limits."""
    if len(hull.vertices) <= 64 and _polygon_count(hull) <= 64:
        # Remove interior/copanar points introduced by triangulation-edge cuts.
        return [_hull(hull.points[hull.vertices])]
    # A longitudinal cut may retain all curved side faces; choose the spatial
    # bisection that reduces the largest child vertex/polygon count most.
    candidates = [_bisect_hull(hull, axis) for axis in range(3)]
    children = min(candidates, key=lambda pair: max(
        max(len(child.vertices), _polygon_count(child)) for child in pair))
    return [part for child in children for part in _gpu_convex_parts(child)]


def _moments(hull):
    """Integral of (1, x, xx^T), using positive tetrahedra about an interior point."""
    origin = hull.points[hull.vertices].mean(axis=0)
    tetra = np.concatenate((np.broadcast_to(origin, (len(hull.simplices), 1, 3)), hull.points[hull.simplices]), axis=1)
    volume = np.abs(np.linalg.det(tetra[:, 1:]-tetra[:, :1]))/6
    sums = tetra.sum(axis=1)
    first = (volume[:, None]*sums/4).sum(axis=0)
    second = (volume[:, None, None]*(np.einsum('ni,nj->nij', sums, sums)+np.einsum('nki,nkj->nij', tetra, tetra))/20).sum(axis=0)
    return np.array(volume.sum()), first, second


def _intersection(a, b):
    """Exact convex-polyhedron intersection vertices; no voxel overlap counting."""
    if np.any(a.points.min(0) >= b.points.max(0)) or np.any(b.points.min(0) >= a.points.max(0)):
        return None
    result = []
    for source, other in ((a, b), (b, a)):
        points = source.points
        planes = other.equations
        distance = points @ planes[:, :3].T + planes[:, 3]
        result.extend(points[np.all(distance <= 1.e-11, axis=1)])
        edges = np.unique(np.sort(np.concatenate([source.simplices[:, [0, 1]], source.simplices[:, [1, 2]], source.simplices[:, [2, 0]]]), axis=1), axis=0)
        d0, d1 = distance[edges[:, 0]], distance[edges[:, 1]]
        crossing = (d0*d1 < 0.)
        ei, pi = np.nonzero(crossing)
        t = d0[ei, pi]/(d0[ei, pi]-d1[ei, pi])
        candidates = points[edges[ei, 0]]+t[:, None]*(points[edges[ei, 1]]-points[edges[ei, 0]])
        inside = np.all(candidates @ planes[:, :3].T + planes[:, 3] <= 1.e-11, axis=1)
        result.extend(candidates[inside])
    if len(result) < 4:
        return None
    points = np.unique(np.round(result, 13), axis=0)
    if np.linalg.matrix_rank(points-points[0], tol=1.e-11) < 3:
        return None  # A shared face has zero mass.
    return _hull(points)


def normalize_handle_metadata(metadata):
    """Convert authored Sdf numeric arrays to JSON/config-safe Python lists."""
    result = dict(metadata)
    for key in (
        "free_interval_m", "centre_interval_m", "grasp_position_local_m",
        "grasp_quaternion_wxyz", "bounds_min_local_m", "bounds_max_local_m",
        "center_of_mass_local_m", "inertia_diagonal_kg_m2", "inertia_axes_wxyz",
        "inertia_tensor_kg_m2",
    ):
        if key in result:
            result[key] = list(result[key])
    return result


def build_handle_geometry(parameters, door_open_lr):
    """Return local convex cells, explicit mass properties and the unique inside G."""
    p = normalize_handle_metadata(parameters)
    family, scale = p["family"], p["plane_scale"]
    if p["version"] != 29 or door_open_lr not in (-1, 1):
        raise ValueError("B05 requires v29 parameters and a signed door side")
    interval = _free_interval(family)*scale
    centre_interval = interval + np.array([.031, -.031])
    if centre_interval[1] <= centre_interval[0]:
        raise ValueError("B05 grasp-centre interval is empty")
    sg = centre_interval.mean()
    qg = brentq(lambda q: _arc(family, q)*scale-sg, 0., 1.)
    pg2, tg2 = _curve(family, qg)
    tg2 /= np.linalg.norm(tg2)
    pg = np.array([-(.020+p["face_standoff_m"]), -door_open_lr*pg2[0]*scale, pg2[1]*scale])
    e = np.array([0., -door_open_lr*tg2[0], tg2[1]])
    approach = np.array([1., 0., 0.])
    rotation = np.column_stack((e, np.cross(-e, approach), approach))
    quat = Rotation.from_matrix(rotation).as_quat()[[3, 0, 1, 2]]
    ph = p["section_roll_rad"]
    a, b, r = p["section_normal_diameter_m"]/2, p["section_closing_diameter_m"]/2, p["corner_radius_m"]
    normal_support = (a-r)*abs(np.cos(ph))+(b-r)*abs(np.sin(ph))+r if family == "F2" else np.hypot(a*np.cos(ph), b*np.sin(ph))
    closing_support = (a-r)*abs(np.sin(ph))+(b-r)*abs(np.cos(ph))+r if family == "F2" else np.hypot(a*np.sin(ph), b*np.cos(ph))
    p.update(free_interval_m=interval.tolist(), centre_interval_m=centre_interval.tolist(), grasp_arc_m=float(sg),
             grasp_position_local_m=pg.tolist(), grasp_quaternion_wxyz=quat.tolist(),
             grasp_normal_half_extent_m=float(normal_support), grasp_closing_half_extent_m=float(closing_support),
             main_arc_length_m=float(_arc(family, 1.)*scale), axle_length_m=.040+2*p["face_standoff_m"])
    steps = 1 if family in ("F0", "F1", "F2") else 8 if family in ("F3", "X1", "F6") else 16
    qs = np.linspace(0., 1., steps+1)
    if family == "F5":
        qs = np.unique(np.r_[qs, .032/.140, .108/.140])
    curve, tangent = _curve(family, qs)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    cells = []
    for side, label in ((-1, "inside"), (1, "outside")):
        n = np.array([float(side), 0., 0.])
        centres = np.c_[np.full(len(qs), side*p["axle_length_m"]/2), -door_open_lr*curve[:, 0]*scale, curve[:, 1]*scale]
        tangents = np.c_[np.zeros(len(qs)), -door_open_lr*tangent[:, 0], tangent[:, 1]]
        normals = np.repeat(n[None], len(qs), axis=0)
        sections = [_section(p, q) for q in qs]
        if p["return_present"]:
            pe, te, radius = centres[-1].copy(), tangents[-1].copy(), p["return_radius_m"]
            for theta in np.linspace(0., np.pi/2, 9)[1:]:
                centres = np.vstack((centres, pe+radius*np.sin(theta)*te-radius*(1-np.cos(theta))*n))
                tangents = np.vstack((tangents, np.cos(theta)*te-np.sin(theta)*n))
                normals = np.vstack((normals, np.cos(theta)*n+np.sin(theta)*te))
                sections.append(_section(p, 1.))
            tail = p["return_depth_m"]-radius
            if tail > 0.:
                centres = np.vstack((centres, centres[-1]-tail*n))
                tangents = np.vstack((tangents, -n))
                normals = np.vstack((normals, te))
                sections.append(_section(p, 1.))
        rings = [centre+section[:, :1]*normal+section[:, 1:]*np.cross(tan, normal)*side
                 for centre, tan, normal, section in zip(centres, tangents, normals, sections)]
        for i in range(len(rings)-1):
            cells.append((f"handle_{label}/segment_{i:02d}", _hull(np.vstack((rings[i], rings[i+1])))))
        for index, sign, name in ((0, -1, "root_cap"), (-1, 1, "tip_cap")):
            extension = p["tip_cap_extension_m"] + (.002 if family == "F6" and index == 0 else 0.)
            # Disjoint convex polar bands share complete end planes. Each ring
            # has <=32 vertices, so a band starts with <=64 vertices.
            cap_rings = [centres[index]+sign*extension*np.sin(theta)*tangents[index]
                         +np.cos(theta)*(rings[index]-centres[index])
                         for theta in np.linspace(0., np.pi/2, 7)[:-1]]
            cap_rings.append((centres[index]+sign*extension*tangents[index])[None])
            for band in range(6):
                cells.append((f"handle_{label}/{name}/band_{band}",
                              _hull(np.vstack((cap_rings[band], cap_rings[band+1])))))
    source_cell_count = len(cells)
    cells = [(f"{name}/part_{index}", part)
             for name, hull in cells for index, part in enumerate(_gpu_convex_parts(hull))]
    angle = np.arange(48)*2*np.pi/48
    axle_ring = np.c_[np.zeros(48), p["neck_radius_m"]*np.cos(angle), p["neck_radius_m"]*np.sin(angle)]
    axle = _hull(np.vstack((axle_ring+[-p["axle_length_m"]/2, 0, 0], axle_ring+[p["axle_length_m"]/2, 0, 0])))
    moments = list(_moments(axle))
    for _, hull in cells:
        for i, value in enumerate(_moments(hull)):
            moments[i] += value
        overlap = _intersection(axle, hull)
        if overlap is not None:
            for i, value in enumerate(_moments(overlap)):
                moments[i] -= value
    mass = .5 if p["return_present"] else .4
    volume, first, second = moments
    com = first/volume
    covariance = second/volume-np.outer(com, com)
    inertia = mass*(np.eye(3)*np.trace(covariance)-covariance)
    eigenvalues, axes = np.linalg.eigh(inertia)
    if np.any(eigenvalues <= 0.):
        raise ValueError("B05 compound inertia is not positive definite")
    if np.linalg.det(axes) < 0.:
        axes[:, 0] *= -1
    all_points = np.vstack([axle.points]+[h.points for _, h in cells])
    p.update(bounds_min_local_m=all_points.min(0).tolist(), bounds_max_local_m=all_points.max(0).tolist(),
             mass_kg=mass, volume_m3=float(volume), center_of_mass_local_m=com.tolist(),
             inertia_diagonal_kg_m2=eigenvalues.tolist(),
             inertia_axes_wxyz=Rotation.from_matrix(axes).as_quat()[[3, 0, 1, 2]].tolist(),
             inertia_tensor_kg_m2=inertia.reshape(-1).tolist(), mass_integration="convex_cells_minus_axle_intersections",
             section_polygon_vertices=len(_section(p, 0.)), cap_polar_steps=6,
             convex_source_cell_count=source_cell_count, convex_cell_count=len(cells),
             convex_additional_partition_count=len(cells)-source_cell_count,
             convex_max_vertices=max(len(h.vertices) for _, h in cells),
             convex_max_polygons=max(_polygon_count(h) for _, h in cells),
             convex_hull_vertex_limit=64, convex_min_thickness_m=0.)
    return p, cells, axle


def author_handle_geometry(stage, handle_path, panel_path, parameters, door_open_lr,
                           handle_y, handle_z, door_width, door_height, door_mass):
    """Author the same cells as visual/collision, and explicit compound rigid mass."""
    from pxr import Gf, UsdGeom, UsdPhysics
    p, cells, axle = build_handle_geometry(parameters, door_open_lr)
    # Straight circular main lever uses the native Capsule; its polyhedral integration
    # uses the same 32-sided section / 6-step cap discretisation as the other families.
    native_capsule = p["family"] == "F0" and not p["return_present"]
    if native_capsule:
        for side, label in ((-1, "inside"), (1, "outside")):
            capsule = UsdGeom.Capsule.Define(stage, f"{handle_path}/handle_{label}")
            capsule.CreateAxisAttr("Y")
            capsule.CreateRadiusAttr(p["section_normal_diameter_m"]/2)
            capsule.CreateHeightAttr(p["main_arc_length_m"])
            UsdGeom.Xformable(capsule).AddTranslateOp().Set(Gf.Vec3d(side*p["axle_length_m"]/2, -door_open_lr*p["main_arc_length_m"]/2, 0.))
            UsdPhysics.CollisionAPI.Apply(capsule.GetPrim()).CreateCollisionEnabledAttr(True)
    else:
        for name, hull in cells:
            mesh = UsdGeom.Mesh.Define(stage, f"{handle_path}/{name}")
            # Hull triangulation is outward-oriented explicitly (Qhull simplex winding is arbitrary).
            triangles = hull.simplices.copy()
            vertices = hull.points[triangles]
            reverse = np.einsum('ij,ij->i', np.cross(vertices[:, 1]-vertices[:, 0], vertices[:, 2]-vertices[:, 0]), hull.equations[:, :3]) < 0
            triangles[reverse] = triangles[reverse][:, [0, 2, 1]]
            mesh.CreatePointsAttr([Gf.Vec3f(*point) for point in hull.points])
            mesh.CreateFaceVertexCountsAttr([3]*len(triangles))
            mesh.CreateFaceVertexIndicesAttr(triangles.reshape(-1).tolist())
            mesh.CreateSubdivisionSchemeAttr("none")
            UsdPhysics.CollisionAPI.Apply(mesh.GetPrim()).CreateCollisionEnabledAttr(True)
            UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr("convexHull")
            mesh.GetPrim().ApplyAPI("PhysxConvexHullCollisionAPI")
            mesh.GetPrim().GetAttribute("physxConvexHullCollision:hullVertexLimit").Set(64)
            # The final polar band is thinner than the schema's 1 mm default.
            mesh.GetPrim().GetAttribute("physxConvexHullCollision:minThickness").Set(0.)
    cylinder = UsdGeom.Cylinder.Define(stage, f"{handle_path}/axle")
    cylinder.CreateAxisAttr("X")
    cylinder.CreateHeightAttr(p["axle_length_m"])
    cylinder.CreateRadiusAttr(p["neck_radius_m"])
    UsdPhysics.CollisionAPI.Apply(cylinder.GetPrim()).CreateCollisionEnabledAttr(True)
    mass_api = UsdPhysics.MassAPI.Apply(stage.GetPrimAtPath(handle_path))
    mass_api.CreateMassAttr(p["mass_kg"])
    mass_api.CreateCenterOfMassAttr(Gf.Vec3f(*p["center_of_mass_local_m"]))
    mass_api.CreateDiagonalInertiaAttr(Gf.Vec3f(*p["inertia_diagonal_kg_m2"]))
    q = p["inertia_axes_wxyz"]
    mass_api.CreatePrincipalAxesAttr(Gf.Quatf(q[0], Gf.Vec3f(*q[1:])))
    # Rose volumes join the panel at their bases; density is shared with the panel,
    # so the two plates redistribute the fixed B01 mass instead of increasing it.
    panel_volume = .040*(door_width-.004)*(door_height-.004)
    rose_volume = np.pi*.027**2*.006
    density = door_mass/(panel_volume+2*rose_volume)
    panel_shape = stage.GetPrimAtPath(f"{panel_path}/panel")
    UsdPhysics.MassAPI.Apply(panel_shape).CreateMassAttr(density*panel_volume)
    for side, label in ((-1, "inside"), (1, "outside")):
        rose = UsdGeom.Cylinder.Define(stage, f"{panel_path}/rose_{label}")
        rose.CreateAxisAttr("X")
        rose.CreateHeightAttr(.006)
        rose.CreateRadiusAttr(.027)
        UsdGeom.Xformable(rose).AddTranslateOp().Set(Gf.Vec3d(side*.023, handle_y, handle_z))
        UsdPhysics.CollisionAPI.Apply(rose.GetPrim()).CreateCollisionEnabledAttr(True)
        UsdPhysics.MassAPI.Apply(rose.GetPrim()).CreateMassAttr(density*rose_volume)
    p.update(rose_radius_m=.027, rose_thickness_m=.006, panel_mass_including_roses_kg=float(door_mass))
    return p
