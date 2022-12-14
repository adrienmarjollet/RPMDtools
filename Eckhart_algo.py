#!======================================================================
#!%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
#!%%%%%   Adapted Eckhart transformation for trajectory based
#!%%%%%   ring polymer molecular dynamics (RPMD).
#!%%%%%   See the paper
#!%%%%%   Version 1 (v1):
#!%%%%%   Version 2 (v2):
#!%%%%%   Notations: N is the number of atoms
#!%%%%%              D is the number of spatial dimensions
#!%%%%%              n is the number of beads (replicas)
#!%%%%%              x0 is the position vector of the equilibrium
#!%%%%%                 structure
#!%%%%%   IMPORTANT: Zq is structured such that to access the bead
#!%%%%%              of the Nth atom, jth spatial dimension and
#!%%%%%              kth bead we write:
#!%%%%%                        Zq[ i*D*n + j*n +k ]
#!%%%%%   Note: For the sake of readability, the ring polymer
#!%%%%%   normal-mode transformation is not leveraged here.
#!%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
#!======================================================================
import numpy as np

#!================ Useful functions ====================================


def sortEigValsVecs(evals, evecs):
    """
    Sort the pair (eigvals,eigvecs) from low to high values
    """
    evecs[:] = evecs.take(
        evals.argsort(), axis=1)  # axis=1:eigenvectors are expected in columns
    evals[:] = evals.take(evals.argsort())


def centroids(n, Zq):
    '''Returns centroid coordinates
       Note: n must be even and greater or equal with 4.     
    '''
    return np.array([np.mean(Zq[i*n:i*n+n]) for i in range(len(Zq)//n)])


def bead_coordinates(N, D, n, Zq, k):
    '''Returns the kth bead coordinates
    '''
    return Zq[k:N*D*n+k:n]


def dimension_coordinates(N, D, q, j):
    '''Returns the jth dimensional coordinates
    '''
    return q[j:N*D+j:D]


def center_of_mass(N, D, q, m):
    '''Return the center of mass for a position vector q and mass vector m
       They must have the same length.

       m: mass vector (mass associated to each d.o.f.)
       q: position vector
    '''
    return np.multiply(m / np.sum(m[::D]), q).reshape((N, D)).sum(axis=0)


def coincide_COM(N, D, n, COM, Zq):
    '''Coincide the centroid center of mass with the origin for a system of beads'''
    return np.array([(Zq[j*D:j*D+D]-COM) for j in range(len(Zq)//D)]).flatten()

#!================ Eckhart Algorithms ====================================


def Eckart_Frame_v1(N, D, n, m, Zq, q0):
    '''
    Generalization of the simple Eckhart transformation to the ring polymer phase space.

    Original paper: 

    m: mass vector (of length N*D)

    Zq: position vector of the ring polymer beads (of length N*D*n)
    '''

    X = np.zeros((N, D))
    AT, Ainv, SS, sqrtD, P, PT, T, COM = np.zeros((D, D)), np.zeros((D, D)), np.zeros(
        (D, D)), np.zeros((D, D)), np.zeros((D, D)), np.zeros((D, D)), np.zeros((D, D))

    '''First we need to coindice the center of mass centroid to the origin'''
    COM = center_of_mass(N, D, centroids(N, D, n, Zq), m)

    Zq = coincide_COM(N, D, n, COM, Zq)

    Zq_new = np.zeros(N*D*n)
    '''Loop over the beads'''
    for k in range(n):

        '''q_k is the position matrix for the imaginary time slice k (k=1,...,n)'''
        q_k = bead_coordinates(N, D, n, Zq, k)

        Ak = np.zeros((D, D))

        # LOOP FORMULATION:
        # for j1 in range(D):
        #    for j2 in range(D):
        #        for i in range(N):
        #            Ak[j1, j2] += m[i*D] * q_k[i*D + j1] * x0[i*D + j2]
        # TODO: try to completely vectorize it or apply a jit decorator
        for j1 in range(D):
            for j2 in range(D):
                Ak[j1, j2] = np.dot(m[::D], dimension_coordinates(
                    N, D, q_k, j1)*dimension_coordinates(N, D, q0, j2))

        AT, Ainv = Ak.transpose(), np.linalg.inv(Ak)

        #SS = np.dot(A, AT)
        '''Linear algebra to obtain the rotation matrix T
        '''
        L, P = np.linalg.eig(np.dot(Ak, AT))

        PT = P.transpose()

        np.fill_diagonal(sqrtD, np.sqrt(L))

        T = np.dot(np.dot(Ainv, P), np.dot(sqrtD, PT))

        rot_qk = np.concatenate([np.dot(T, q_k[i*D:i*D+D]) for i in range(N)])

        Zq_new[k:N*D*n+k:n] = rot_qk

    return Zq_new


def overlap(N, D, q, q0, T):
    Tq = np.concatenate([np.dot(T, q[i*D:i*D+D]) for i in range(N)])
    return mp.linalg.norm(Tq - q0)


def Eckart_Frame_v2(N, D, q0, q, m):
    '''More suitable for dynamics (ex: to avoid spurious rotations during an adiabatic switching)
       Computationally more demanding
       Notations remain mainly the same 
    '''

    T = np.matrix([[float(0) for j in range(D)] for i in range(D)])

    A = np.zeros((D, D))
    for j1 in range(D):
        for j2 in range(D):
            A[j1, j2] = np.dot(m[::D], dimension_coordinates(
                N, D, q, j1)*dimension_coordinates(N, D, q0, j2))

    A2 = np.dot(A.transpose(), A)
    A1 = np.dot(A, A.transpose())
    a1, epsi = np.linalg.eig(A1)
    a2, eta = np.linalg.eig(A2)
    sortEigValsVecs(a1, epsi)
    sortEigValsVecs(a2, eta)

    L = [-1, 1]
    s1s2s3_optimal = [0, 0, 0]
    Tq_optimal, lap = np.zeros(N*D), 1e10

    for s1 in L:
        for s2 in L:
            for s3 in L:
                epsi[:, 0] = s1*epsi[:, 0]
                epsi[:, 1] = s2*epsi[:, 1]
                epsi[:, 2] = s3*epsi[:, 2]
                epsi3 = np.cross(np.asarray(
                    epsi[:, 0]).reshape(-1), np.asarray(epsi[:, 1]).reshape(-1))
                eta3 = np.cross(np.asarray(
                    eta[:, 0]).reshape(-1), np.asarray(eta[:, 1]).reshape(-1))
                epsi[:, 2] = np.asarray(epsi3).reshape(3, 1)
                eta[:, 2] = np.asarray(eta3).reshape(3, 1)
                U = epsi.transpose()
                V = eta.transpose()

                T = np.dot(V, U.transpose())

                rot_q = np.concatenate(
                    [np.dot(T, q[i*D:i*D+D]) for i in range(N)])

                ol_s1s2s3 = overlap(N, D, rot_q, q0, T)

                if ol_s1s2s3 < lap:
                    lap = ol_s1s2s3
                    s1s2s3_optimal = [s1, s2, s3]
                    Tq_optimal = rot_q
                else:
                    lap = lap

    return Tq_optimal, s1s2s3_optimal
