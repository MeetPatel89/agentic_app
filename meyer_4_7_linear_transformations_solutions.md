
# Meyer, Section 4.7 — Linear Transformations  
## Fully worked solutions to Exercises 4.7.1–4.7.19

**Source note.** This document solves the exercises from **Section 4.7, “Linear Transformations,”** in *Matrix Analysis and Applied Linear Algebra* by Carl D. Meyer.

## Quick toolbox from Section 4.7

Let $T : U \to V$.

1. $T$ is linear if and only if
   $$
   T(\alpha x + y)=\alpha T(x)+T(y)
   \quad\text{for all }x,y\in U,\ \alpha\in\mathbb{F}.
   $$

2. If $B=\{u_1,\dots,u_n\}$ is a basis of $U$ and $B'=\{v_1,\dots,v_m\}$ is a basis of $V$, then
   $$
   [T]_{BB'}
   =
   \begin{bmatrix}
   [T(u_1)]_{B'} & [T(u_2)]_{B'} & \cdots & [T(u_n)]_{B'}
   \end{bmatrix}.
   $$

3. The action of $T$ becomes matrix multiplication in coordinates:
   $$
   [T(u)]_{B'}=[T]_{BB'}[u]_B.
   $$

4. If $L:V\to W$ is also linear, then
   $$
   [LT]_{BB''}=[L]_{B'B''}[T]_{BB'}.
   $$

5. If $T:U\to U$ is invertible, then
   $$
   [T^{-1}]_B=[T]_B^{-1}.
   $$

---

## Exercise 4.7.1

Determine which of the following maps are **linear operators** on $\mathbb{R}^2$:

$$
\begin{aligned}
(a)\;&T(x,y)=(x,1+y),\\
(b)\;&T(x,y)=(y,x),\\
(c)\;&T(x,y)=(0,xy),\\
(d)\;&T(x,y)=(x^2,y^2),\\
(e)\;&T(x,y)=(x,\sin y),\\
(f)\;&T(x,y)=(x+y,x-y).
\end{aligned}
$$

### Solution

A map is a linear operator on $\mathbb{R}^2$ if it maps $\mathbb{R}^2$ into itself **and** satisfies
$$
T(\alpha u+v)=\alpha T(u)+T(v).
$$
A quick necessary test is $T(0,0)=(0,0)$.

#### (a) $T(x,y)=(x,1+y)$

$$
T(0,0)=(0,1)\neq(0,0).
$$
So $T$ is **not** linear.

#### (b) $T(x,y)=(y,x)$

Let $u=(x_1,y_1)$, $v=(x_2,y_2)$, and $\alpha\in\mathbb{R}$. Then
$$
T(\alpha u+v)
=
T(\alpha x_1+x_2,\alpha y_1+y_2)
=
(\alpha y_1+y_2,\alpha x_1+x_2).
$$
On the other hand,
$$
\alpha T(u)+T(v)
=
\alpha(y_1,x_1)+(y_2,x_2)
=
(\alpha y_1+y_2,\alpha x_1+x_2).
$$
The two expressions agree, so $T$ is linear.

#### (c) $T(x,y)=(0,xy)$

Take $u=(1,1)$ and $v=(1,1)$. Then
$$
T(u+v)=T(2,2)=(0,4),
$$
but
$$
T(u)+T(v)=(0,1)+(0,1)=(0,2).
$$
Since $T(u+v)\neq T(u)+T(v)$, $T$ is **not** linear.

#### (d) $T(x,y)=(x^2,y^2)$

Take $u=(1,0)$ and $\alpha=2$. Then
$$
T(2u)=T(2,0)=(4,0),
$$
whereas
$$
2T(u)=2(1,0)=(2,0).
$$
So homogeneity fails, and $T$ is **not** linear.

#### (e) $T(x,y)=(x,\sin y)$

Take $u=(0,\pi/2)$ and $\alpha=2$. Then
$$
T(2u)=T(0,\pi)=(0,0),
$$
but
$$
2T(u)=2(0,1)=(0,2).
$$
So $T$ is **not** linear.

#### (f) $T(x,y)=(x+y,x-y)$

Let $u=(x_1,y_1)$, $v=(x_2,y_2)$. Then
$$
\begin{aligned}
T(\alpha u+v)
&=
T(\alpha x_1+x_2,\alpha y_1+y_2)\\
&=
(\alpha x_1+x_2+\alpha y_1+y_2,\ \alpha x_1+x_2-(\alpha y_1+y_2))\\
&=
(\alpha(x_1+y_1)+(x_2+y_2),\ \alpha(x_1-y_1)+(x_2-y_2))\\
&=
\alpha T(u)+T(v).
\end{aligned}
$$
So $T$ is linear.

### Final answer

The linear operators are

$$
\boxed{(b)\text{ and }(f).}
$$

---

## Exercise 4.7.2

For $A\in\mathbb{R}^{n\times n}$, determine which of the following are linear transformations:

$$
\begin{aligned}
(a)\;&T(X)=AX-XA,\\
(b)\;&T(x)=Ax+b \quad (b\neq 0),\\
(c)\;&T(A)=A^T,\\
(d)\;&T(X)=\frac{X+X^T}{2}.
\end{aligned}
$$

### Solution

We interpret (a), (c), and (d) as maps on $\mathbb{R}^{n\times n}$, and (b) as a map on $\mathbb{R}^{n\times 1}$.

#### (a) $T(X)=AX-XA$

Take matrices $X,Y$ and scalar $\alpha$. Then
$$
\begin{aligned}
T(\alpha X+Y)
&=A(\alpha X+Y)-(\alpha X+Y)A\\
&=\alpha AX+AY-\alpha XA-YA\\
&=\alpha(AX-XA)+(AY-YA)\\
&=\alpha T(X)+T(Y).
\end{aligned}
$$
So this map is linear.

#### (b) $T(x)=Ax+b$ with $b\neq 0$

Check the zero vector:
$$
T(0)=A0+b=b\neq 0.
$$
Therefore $T$ is **not** linear.

#### (c) $T(X)=X^T$

For matrices $X,Y$ and scalar $\alpha$,
$$
T(\alpha X+Y)=(\alpha X+Y)^T=\alpha X^T+Y^T=\alpha T(X)+T(Y).
$$
So transpose is linear.

#### (d) $T(X)=\dfrac{X+X^T}{2}$

Again,
$$
\begin{aligned}
T(\alpha X+Y)
&=\frac{(\alpha X+Y)+(\alpha X+Y)^T}{2}\\
&=\frac{\alpha X+Y+\alpha X^T+Y^T}{2}\\
&=\alpha\frac{X+X^T}{2}+\frac{Y+Y^T}{2}\\
&=\alpha T(X)+T(Y).
\end{aligned}
$$
So this map is linear.

### Final answer

The linear transformations are

$$
\boxed{(a),\ (c),\ \text{and }(d).}
$$

---

## Exercise 4.7.3

Explain why $T(0)=0$ for every linear transformation $T$.

### Solution

Because $T$ is linear,
$$
T(0)=T(0x)=0\,T(x)=0
$$
for every $x$ in the domain.

Another standard argument is
$$
0=x-x
\quad\Longrightarrow\quad
T(0)=T(x-x)=T(x)-T(x)=0.
$$

So every linear transformation must map the zero vector to the zero vector:

$$
\boxed{T(0)=0.}
$$

---

## Exercise 4.7.4

Determine which of the following are linear operators on $P_n$, the space of polynomials of degree at most $n$.

### (a)
$$
T=\xi_k D^k+\xi_{k-1}D^{k-1}+\cdots+\xi_1D+\xi_0I,
$$
where $D^j$ means the $j$-th derivative operator.

### (b)
$$
T(p)(t)=t^n p'(0)+t.
$$

### Solution

#### (a)

Each derivative operator $D^j$ is linear:
$$
D^j(\alpha p+q)=\alpha D^j p+D^j q.
$$
The identity operator $I$ is also linear. A linear combination of linear operators is linear, so
$$
T=\xi_k D^k+\xi_{k-1}D^{k-1}+\cdots+\xi_1D+\xi_0I
$$
is linear.

Also, $D^j p\in P_n$ for every $p\in P_n$ (in fact its degree drops), so $T$ maps $P_n$ into $P_n$. Therefore $T$ is a linear operator on $P_n$.

#### (b)

The term $t^n p'(0)$ is linear in $p$, because $p\mapsto p'(0)$ is a linear functional and multiplication by $t^n$ is linear.

However, the extra $+\,t$ breaks linearity:
$$
T(0)(t)=t^n\cdot 0+t=t\neq 0.
$$
So this map is **not** linear.

### Final answer

$$
\boxed{\text{(a) is linear; (b) is not linear.}}
$$

---

## Exercise 4.7.5

Let $v$ be a fixed vector in $\mathbb{R}^{n\times 1}$, and define
$$
T(x)=v^T x.
$$

### (a) Is $T$ a linear operator?  
### (b) Is $T$ a linear transformation?

### Solution

#### (a) Linear operator?

A linear **operator** must map a vector space into itself. Here
$$
T:\mathbb{R}^{n\times 1}\to \mathbb{R},
$$
because $v^T x$ is a scalar. The codomain is not $\mathbb{R}^{n\times 1}$, so $T$ is **not** a linear operator on $\mathbb{R}^{n\times 1}$.

#### (b) Linear transformation?

Yes. For vectors $x,y$ and scalar $\alpha$,
$$
T(\alpha x+y)=v^T(\alpha x+y)=\alpha v^T x+v^T y=\alpha T(x)+T(y).
$$
So $T$ is linear as a map from $\mathbb{R}^{n\times 1}$ into $\mathbb{R}$.

It is therefore a linear transformation (more specifically, a linear functional).

### Final answer

$$
\boxed{\text{(a) No, \quad (b) Yes.}}
$$

---

## Exercise 4.7.6

For
$$
T(x,y)=(x+y,-2x+4y),
$$
determine $[T]_B$ for the basis
$$
B=\left\{
u_1=\begin{bmatrix}1\\1\end{bmatrix},
u_2=\begin{bmatrix}1\\2\end{bmatrix}
\right\}.
$$

### Solution

By definition, the columns of $[T]_B$ are $[T(u_1)]_B$ and $[T(u_2)]_B$.

First compute $T(u_1)$:
$$
T(1,1)=(2,2)=2\begin{bmatrix}1\\1\end{bmatrix}+0\begin{bmatrix}1\\2\end{bmatrix}
=2u_1+0u_2.
$$
So
$$
[T(u_1)]_B=\begin{bmatrix}2\\0\end{bmatrix}.
$$

Now compute $T(u_2)$:
$$
T(1,2)=(3,6).
$$
Write this in the basis $B$:
$$
a u_1+b u_2=(3,6).
$$
That is,
$$
a\begin{bmatrix}1\\1\end{bmatrix}+b\begin{bmatrix}1\\2\end{bmatrix}
=
\begin{bmatrix}3\\6\end{bmatrix},
$$
so
$$
\begin{cases}
a+b=3,\\
a+2b=6.
\end{cases}
$$
Subtracting gives $b=3$, and then $a=0$. Hence
$$
T(u_2)=0u_1+3u_2,
\qquad
[T(u_2)]_B=\begin{bmatrix}0\\3\end{bmatrix}.
$$

Therefore
$$
[T]_B=
\begin{bmatrix}
2 & 0\\
0 & 3
\end{bmatrix}.
$$

### Final answer

$$
\boxed{
[T]_B=
\begin{bmatrix}
2 & 0\\
0 & 3
\end{bmatrix}
}.
$$

---

## Exercise 4.7.7

Let
$$
T(x,y)=(x+3y,\,0,\,2x-4y).
$$

### (a) Determine $[T]_{SS'}$, where $S$ is the standard basis of $\mathbb{R}^2$ and $S'$ is the standard basis of $\mathbb{R}^3$.

### (b) Determine $[T]_{SS''}$, where
$$
S''=\{e_3,e_2,e_1\}
$$
is the permuted standard basis of $\mathbb{R}^3$.

### Solution

Let
$$
e_1=\begin{bmatrix}1\\0\end{bmatrix},
\qquad
e_2=\begin{bmatrix}0\\1\end{bmatrix}.
$$

### (a) Matrix relative to standard bases

Compute the images of the domain basis vectors:
$$
T(e_1)=T(1,0)=\begin{bmatrix}1\\0\\2\end{bmatrix},
\qquad
T(e_2)=T(0,1)=\begin{bmatrix}3\\0\\-4\end{bmatrix}.
$$
Since $S'$ is standard, those are already the coordinate columns. Therefore
$$
[T]_{SS'}
=
\begin{bmatrix}
1 & 3\\
0 & 0\\
2 & -4
\end{bmatrix}.
$$

### (b) Matrix relative to $S''=\{e_3,e_2,e_1\}$

A vector $(a,b,c)^T$ has coordinates
$$
[(a,b,c)^T]_{S''}=
\begin{bmatrix}
c\\
b\\
a
\end{bmatrix},
$$
because
$$
(a,b,c)^T = c\,e_3+b\,e_2+a\,e_1.
$$

So
$$
[T(e_1)]_{S''}
=
\left[\begin{array}{c}1\\0\\2\end{array}\right]_{S''}
=
\begin{bmatrix}2\\0\\1\end{bmatrix},
\qquad
[T(e_2)]_{S''}
=
\left[\begin{array}{c}3\\0\\-4\end{array}\right]_{S''}
=
\begin{bmatrix}-4\\0\\3\end{bmatrix}.
$$
Hence
$$
[T]_{SS''}
=
\begin{bmatrix}
2 & -4\\
0 & 0\\
1 & 3
\end{bmatrix}.
$$

### Final answer

$$
\boxed{
[T]_{SS'}
=
\begin{bmatrix}
1 & 3\\
0 & 0\\
2 & -4
\end{bmatrix},
\qquad
[T]_{SS''}
=
\begin{bmatrix}
2 & -4\\
0 & 0\\
1 & 3
\end{bmatrix}.
}
$$

---

## Exercise 4.7.8

Let $T:\mathbb{R}^3\to\mathbb{R}^3$ be
$$
T(x,y,z)=(x-y,\ y-x,\ x-z),
$$
and let
$$
v=\begin{bmatrix}1\\1\\2\end{bmatrix},
\qquad
B=\left\{
b_1=\begin{bmatrix}1\\0\\1\end{bmatrix},
b_2=\begin{bmatrix}0\\1\\1\end{bmatrix},
b_3=\begin{bmatrix}1\\1\\0\end{bmatrix}
\right\}.
$$

### (a) Determine $[T]_B$ and $[v]_B$.

### (b) Compute $[T(v)]_B$ and verify
$$
[T]_B[v]_B=[T(v)]_B.
$$

### Solution

### Step 1: Find $[v]_B$

Write
$$
v=c_1b_1+c_2b_2+c_3b_3.
$$
Then
$$
c_1\begin{bmatrix}1\\0\\1\end{bmatrix}
+
c_2\begin{bmatrix}0\\1\\1\end{bmatrix}
+
c_3\begin{bmatrix}1\\1\\0\end{bmatrix}
=
\begin{bmatrix}1\\1\\2\end{bmatrix}.
$$
This gives the system
$$
\begin{cases}
c_1+c_3=1,\\
c_2+c_3=1,\\
c_1+c_2=2.
\end{cases}
$$
From the third equation and the first two, we get $c_3=0$, hence $c_1=1$, $c_2=1$. So
$$
[v]_B=\begin{bmatrix}1\\1\\0\end{bmatrix}.
$$

### Step 2: Find the columns of $[T]_B$

We compute $T(b_1)$, $T(b_2)$, $T(b_3)$ and rewrite each in the basis $B$.

#### First column: $T(b_1)$

$$
T(1,0,1)=(1,-1,0).
$$
Now solve
$$
a_1b_1+a_2b_2+a_3b_3=\begin{bmatrix}1\\-1\\0\end{bmatrix}.
$$
That is,
$$
\begin{cases}
a_1+a_3=1,\\
a_2+a_3=-1,\\
a_1+a_2=0.
\end{cases}
$$
A quick check gives $a_1=1$, $a_2=-1$, $a_3=0$. Thus
$$
[T(b_1)]_B=\begin{bmatrix}1\\-1\\0\end{bmatrix}.
$$

#### Second column: $T(b_2)$

$$
T(0,1,1)=(-1,1,-1).
$$
Solve
$$
a_1b_1+a_2b_2+a_3b_3=\begin{bmatrix}-1\\1\\-1\end{bmatrix}.
$$
This gives
$$
\begin{cases}
a_1+a_3=-1,\\
a_2+a_3=1,\\
a_1+a_2=-1.
\end{cases}
$$
From the first and third equations,
$$
a_2-a_3=0 \quad\Rightarrow\quad a_2=a_3.
$$
Using the second equation,
$$
2a_3=1 \quad\Rightarrow\quad a_3=\frac12,\quad a_2=\frac12.
$$
Then from $a_1+a_3=-1$,
$$
a_1=-1-\frac12=-\frac32.
$$
So
$$
[T(b_2)]_B=\begin{bmatrix}-\frac32\\[3pt]\frac12\\[3pt]\frac12\end{bmatrix}.
$$

#### Third column: $T(b_3)$

$$
T(1,1,0)=(0,0,1).
$$
Solve
$$
a_1b_1+a_2b_2+a_3b_3=\begin{bmatrix}0\\0\\1\end{bmatrix},
$$
so
$$
\begin{cases}
a_1+a_3=0,\\
a_2+a_3=0,\\
a_1+a_2=1.
\end{cases}
$$
From the first two equations, $a_1=a_2=-a_3$. Then the third gives
$$
-2a_3=1 \quad\Rightarrow\quad a_3=-\frac12,
$$
hence
$$
a_1=a_2=\frac12.
$$
Therefore
$$
[T(b_3)]_B=\begin{bmatrix}\frac12\\[3pt]\frac12\\[3pt]-\frac12\end{bmatrix}.
$$

So the coordinate matrix is
$$
[T]_B=
\begin{bmatrix}
1 & -\frac32 & \frac12\\
-1 & \frac12 & \frac12\\
0 & \frac12 & -\frac12
\end{bmatrix}.
$$

### Step 3: Compute $[T(v)]_B$

First compute $T(v)$:
$$
T(1,1,2)=(0,0,-1).
$$
Now write
$$
(0,0,-1)=a_1b_1+a_2b_2+a_3b_3.
$$
This gives
$$
\begin{cases}
a_1+a_3=0,\\
a_2+a_3=0,\\
a_1+a_2=-1.
\end{cases}
$$
Again $a_1=a_2=-a_3$, so
$$
-2a_3=-1 \quad\Rightarrow\quad a_3=\frac12,
$$
and therefore
$$
a_1=a_2=-\frac12.
$$
Hence
$$
[T(v)]_B=
\begin{bmatrix}
-\frac12\\[3pt]
-\frac12\\[3pt]
\frac12
\end{bmatrix}.
$$

### Step 4: Verify $[T]_B[v]_B=[T(v)]_B$

Since
$$
[v]_B=\begin{bmatrix}1\\1\\0\end{bmatrix},
$$
we have
$$
[T]_B[v]_B
=
\begin{bmatrix}
1 & -\frac32 & \frac12\\
-1 & \frac12 & \frac12\\
0 & \frac12 & -\frac12
\end{bmatrix}
\begin{bmatrix}1\\1\\0\end{bmatrix}
=
\begin{bmatrix}
1-\frac32\\[3pt]
-1+\frac12\\[3pt]
0+\frac12
\end{bmatrix}
=
\begin{bmatrix}
-\frac12\\[3pt]
-\frac12\\[3pt]
\frac12
\end{bmatrix}
=
[T(v)]_B.
$$

### Final answer

$$
\boxed{
[T]_B=
\begin{bmatrix}
1 & -\frac32 & \frac12\\
-1 & \frac12 & \frac12\\
0 & \frac12 & -\frac12
\end{bmatrix},
\qquad
[v]_B=
\begin{bmatrix}1\\1\\0\end{bmatrix},
\qquad
[T(v)]_B=
\begin{bmatrix}
-\frac12\\[3pt]
-\frac12\\[3pt]
\frac12
\end{bmatrix}.
}
$$

And indeed
$$
\boxed{[T]_B[v]_B=[T(v)]_B.}
$$

---

## Exercise 4.7.9

Let $A\in\mathbb{R}^{n\times n}$, and let $T:\mathbb{R}^{n\times 1}\to\mathbb{R}^{n\times 1}$ be defined by
$$
T(x)=Ax.
$$
Show that, with respect to the standard basis $S$,
$$
[T]_S=A.
$$

### Solution

The standard basis is $S=\{e_1,\dots,e_n\}$. By definition,
$$
[T]_S=
\begin{bmatrix}
[T(e_1)]_S & [T(e_2)]_S & \cdots & [T(e_n)]_S
\end{bmatrix}.
$$
But
$$
T(e_j)=Ae_j.
$$
Multiplying a matrix by $e_j$ picks out the $j$-th column of the matrix, so
$$
Ae_j=A_{\ast j}.
$$
Since the basis is standard, the coordinate vector of $A_{\ast j}$ is just the column itself. Therefore the $j$-th column of $[T]_S$ is exactly the $j$-th column of $A$. Hence
$$
[T]_S=A.
$$

### Final answer

$$
\boxed{[T]_S=A.}
$$

---

## Exercise 4.7.10

If $T$ is a linear operator on a space $V$ with basis $B$, explain why
$$
[T^k]_B=[T]_B^k
\quad\text{for all integers }k\ge 0.
$$

### Solution

We use the composition rule from Section 4.7:
$$
[LT]_B=[L]_B[T]_B
$$
whenever $L$ and $T$ are operators on the same space.

### Base case: $k=0$

By convention,
$$
T^0=I.
$$
Therefore
$$
[T^0]_B=[I]_B=I=[T]_B^0.
$$

### First few cases

$$
[T^1]_B=[T]_B,
$$
and
$$
[T^2]_B=[TT]_B=[T]_B[T]_B=[T]_B^2.
$$

### Induction step

Assume
$$
[T^k]_B=[T]_B^k.
$$
Then
$$
[T^{k+1}]_B=[T\,T^k]_B=[T]_B[T^k]_B=[T]_B[T]_B^k=[T]_B^{k+1}.
$$

So by induction,
$$
\boxed{[T^k]_B=[T]_B^k \text{ for all }k\ge 0.}
$$

---

## Exercise 4.7.11

Let $P$ be the projector that maps each point in $\mathbb{R}^2$ to its orthogonal projection onto the line $y=x$.

### (a) Determine the coordinate matrix of $P$ with respect to the standard basis.

### (b) Determine the orthogonal projection of
$$
v=\begin{bmatrix}\alpha\\ \beta\end{bmatrix}
$$
onto the line $y=x$.

### Solution

The line $y=x$ is spanned by
$$
u=\begin{bmatrix}1\\1\end{bmatrix}.
$$
The orthogonal projection of $v$ onto $\operatorname{span}\{u\}$ is
$$
P(v)=\frac{v\cdot u}{u\cdot u}\,u.
$$

Since
$$
u\cdot u = 1^2+1^2=2,
$$
we obtain for $v=\begin{bmatrix}x\\y\end{bmatrix}$,
$$
P(v)=\frac{x+y}{2}\begin{bmatrix}1\\1\end{bmatrix}
=
\begin{bmatrix}
\dfrac{x+y}{2}\\[6pt]
\dfrac{x+y}{2}
\end{bmatrix}.
$$

### (a) Matrix relative to the standard basis

Apply $P$ to the basis vectors:
$$
P(e_1)=P\!\left(\begin{bmatrix}1\\0\end{bmatrix}\right)
=
\begin{bmatrix}1/2\\1/2\end{bmatrix},
\qquad
P(e_2)=P\!\left(\begin{bmatrix}0\\1\end{bmatrix}\right)
=
\begin{bmatrix}1/2\\1/2\end{bmatrix}.
$$
Therefore
$$
[P]_S=
\begin{bmatrix}
1/2 & 1/2\\
1/2 & 1/2
\end{bmatrix}.
$$

### (b) Projection of $\begin{bmatrix}\alpha\\ \beta\end{bmatrix}$

Substitute $x=\alpha$, $y=\beta$:
$$
P\!\left(\begin{bmatrix}\alpha\\ \beta\end{bmatrix}\right)
=
\frac{\alpha+\beta}{2}\begin{bmatrix}1\\1\end{bmatrix}
=
\begin{bmatrix}
\dfrac{\alpha+\beta}{2}\\[6pt]
\dfrac{\alpha+\beta}{2}
\end{bmatrix}.
$$

### Final answer

$$
\boxed{
[P]_S=
\begin{bmatrix}
1/2 & 1/2\\
1/2 & 1/2
\end{bmatrix},
\qquad
P\!\left(\begin{bmatrix}\alpha\\ \beta\end{bmatrix}\right)
=
\begin{bmatrix}
\dfrac{\alpha+\beta}{2}\\[6pt]
\dfrac{\alpha+\beta}{2}
\end{bmatrix}.
}
$$

---

## Exercise 4.7.12

For the standard basis
$$
S=\{E_{11},E_{12},E_{21},E_{22}\}
$$
of $\mathbb{R}^{2\times 2}$, determine $[T]_S$ for each operator below, and verify
$$
[T(U)]_S=[T]_S[U]_S
$$
for
$$
U=\begin{bmatrix}a&b\\ c&d\end{bmatrix}.
$$

We use the basis order
$$
E_{11}=
\begin{bmatrix}1&0\\0&0\end{bmatrix},
\quad
E_{12}=
\begin{bmatrix}0&1\\0&0\end{bmatrix},
\quad
E_{21}=
\begin{bmatrix}0&0\\1&0\end{bmatrix},
\quad
E_{22}=
\begin{bmatrix}0&0\\0&1\end{bmatrix}.
$$
Thus
$$
[U]_S=\begin{bmatrix}a\\ b\\ c\\ d\end{bmatrix}.
$$

### (a) $T(X)=\dfrac{X+X^T}{2}$

Compute the images of the basis matrices.

$$
T(E_{11})=\frac{E_{11}+E_{11}^T}{2}=E_{11}.
$$
So
$$
[T(E_{11})]_S=\begin{bmatrix}1\\0\\0\\0\end{bmatrix}.
$$

$$
T(E_{12})=\frac{E_{12}+E_{21}}{2}
=\frac12E_{12}+\frac12E_{21},
$$
so
$$
[T(E_{12})]_S=\begin{bmatrix}0\\1/2\\1/2\\0\end{bmatrix}.
$$

Similarly,
$$
T(E_{21})=\frac{E_{21}+E_{12}}{2}
=\frac12E_{12}+\frac12E_{21},
$$
so
$$
[T(E_{21})]_S=\begin{bmatrix}0\\1/2\\1/2\\0\end{bmatrix}.
$$

Finally,
$$
T(E_{22})=E_{22},
\qquad
[T(E_{22})]_S=\begin{bmatrix}0\\0\\0\\1\end{bmatrix}.
$$

Therefore
$$
[T]_S=
\begin{bmatrix}
1 & 0 & 0 & 0\\
0 & 1/2 & 1/2 & 0\\
0 & 1/2 & 1/2 & 0\\
0 & 0 & 0 & 1
\end{bmatrix}.
$$

For a general matrix $U$,
$$
T(U)=\frac{U+U^T}{2}
=
\begin{bmatrix}
a & \dfrac{b+c}{2}\\[6pt]
\dfrac{b+c}{2} & d
\end{bmatrix},
$$
so
$$
[T(U)]_S=
\begin{bmatrix}
a\\[3pt]
\dfrac{b+c}{2}\\[6pt]
\dfrac{b+c}{2}\\[6pt]
d
\end{bmatrix}.
$$
Now multiply:
$$
[T]_S[U]_S
=
\begin{bmatrix}
1 & 0 & 0 & 0\\
0 & 1/2 & 1/2 & 0\\
0 & 1/2 & 1/2 & 0\\
0 & 0 & 0 & 1
\end{bmatrix}
\begin{bmatrix}a\\b\\c\\d\end{bmatrix}
=
\begin{bmatrix}
a\\[3pt]
\dfrac{b+c}{2}\\[6pt]
\dfrac{b+c}{2}\\[6pt]
d
\end{bmatrix}
=
[T(U)]_S.
$$

### (b) $T(X)=AX-XA$, where
$$
A=\begin{bmatrix}1&1\\ -1&-1\end{bmatrix}
$$

Again compute basis images.

#### Image of $E_{11}$

$$
AE_{11}=
\begin{bmatrix}1&0\\ -1&0\end{bmatrix},
\qquad
E_{11}A=
\begin{bmatrix}1&1\\ 0&0\end{bmatrix},
$$
hence
$$
T(E_{11})=AE_{11}-E_{11}A=
\begin{bmatrix}0&-1\\ -1&0\end{bmatrix}
=-E_{12}-E_{21}.
$$
So
$$
[T(E_{11})]_S=
\begin{bmatrix}0\\ -1\\ -1\\ 0\end{bmatrix}.
$$

#### Image of $E_{12}$

$$
AE_{12}=
\begin{bmatrix}0&1\\ 0&-1\end{bmatrix},
\qquad
E_{12}A=
\begin{bmatrix}-1&-1\\ 0&0\end{bmatrix},
$$
therefore
$$
T(E_{12})=
\begin{bmatrix}1&2\\ 0&-1\end{bmatrix}
=E_{11}+2E_{12}-E_{22},
$$
so
$$
[T(E_{12})]_S=
\begin{bmatrix}1\\ 2\\ 0\\ -1\end{bmatrix}.
$$

#### Image of $E_{21}$

$$
AE_{21}=
\begin{bmatrix}1&0\\ -1&0\end{bmatrix},
\qquad
E_{21}A=
\begin{bmatrix}0&0\\ 1&1\end{bmatrix},
$$
hence
$$
T(E_{21})=
\begin{bmatrix}1&0\\ -2&-1\end{bmatrix}
=E_{11}-2E_{21}-E_{22},
$$
so
$$
[T(E_{21})]_S=
\begin{bmatrix}1\\ 0\\ -2\\ -1\end{bmatrix}.
$$

#### Image of $E_{22}$

$$
AE_{22}=
\begin{bmatrix}0&1\\ 0&-1\end{bmatrix},
\qquad
E_{22}A=
\begin{bmatrix}0&0\\ -1&-1\end{bmatrix},
$$
therefore
$$
T(E_{22})=
\begin{bmatrix}0&1\\ 1&0\end{bmatrix}
=E_{12}+E_{21},
$$
so
$$
[T(E_{22})]_S=
\begin{bmatrix}0\\ 1\\ 1\\ 0\end{bmatrix}.
$$

Thus
$$
[T]_S=
\begin{bmatrix}
0 & 1 & 1 & 0\\
-1 & 2 & 0 & 1\\
-1 & 0 & -2 & 1\\
0 & -1 & -1 & 0
\end{bmatrix}.
$$

For a general
$$
U=\begin{bmatrix}a&b\\ c&d\end{bmatrix},
$$
we compute
$$
AU=
\begin{bmatrix}
a+c & b+d\\
-a-c & -b-d
\end{bmatrix},
\qquad
UA=
\begin{bmatrix}
a-b & a-b\\
c-d & c-d
\end{bmatrix}.
$$
Subtracting gives
$$
T(U)=AU-UA
=
\begin{bmatrix}
b+c & -a+2b+d\\
-a-2c+d & -b-c
\end{bmatrix}.
$$
Therefore
$$
[T(U)]_S=
\begin{bmatrix}
b+c\\
-a+2b+d\\
-a-2c+d\\
-b-c
\end{bmatrix}.
$$
Now multiply:
$$
[T]_S[U]_S=
\begin{bmatrix}
0 & 1 & 1 & 0\\
-1 & 2 & 0 & 1\\
-1 & 0 & -2 & 1\\
0 & -1 & -1 & 0
\end{bmatrix}
\begin{bmatrix}a\\b\\c\\d\end{bmatrix}
=
\begin{bmatrix}
b+c\\
-a+2b+d\\
-a-2c+d\\
-b-c
\end{bmatrix}
=
[T(U)]_S.
$$

### Final answer

$$
\boxed{
[T]_S=
\begin{bmatrix}
1 & 0 & 0 & 0\\
0 & 1/2 & 1/2 & 0\\
0 & 1/2 & 1/2 & 0\\
0 & 0 & 0 & 1
\end{bmatrix}
\quad\text{for }T(X)=\frac{X+X^T}{2},
}
$$

and

$$
\boxed{
[T]_S=
\begin{bmatrix}
0 & 1 & 1 & 0\\
-1 & 2 & 0 & 1\\
-1 & 0 & -2 & 1\\
0 & -1 & -1 & 0
\end{bmatrix}
\quad\text{for }T(X)=AX-XA.
}
$$

In both cases, the identity
$$
\boxed{[T(U)]_S=[T]_S[U]_S}
$$
holds.

---

## Exercise 4.7.13

For $P_2$ and $P_3$, let $S:P_2\to P_3$ be defined by
$$
S(p)=\int_0^t p(x)\,dx.
$$
Determine $[S]_{BB'}$, where
$$
B=\{1,t,t^2\},
\qquad
B'=\{1,t,t^2,t^3\}.
$$

### Solution

By definition, the columns of $[S]_{BB'}$ are the $B'$-coordinates of
$$
S(1),\quad S(t),\quad S(t^2).
$$

Compute them one at a time.

#### First basis vector

$$
S(1)=\int_0^t 1\,dx=t.
$$
Relative to $B'$,
$$
t = 0\cdot 1 + 1\cdot t + 0\cdot t^2 + 0\cdot t^3,
$$
so
$$
[S(1)]_{B'}=\begin{bmatrix}0\\1\\0\\0\end{bmatrix}.
$$

#### Second basis vector

$$
S(t)=\int_0^t x\,dx=\frac{t^2}{2}.
$$
Hence
$$
[S(t)]_{B'}=\begin{bmatrix}0\\0\\1/2\\0\end{bmatrix}.
$$

#### Third basis vector

$$
S(t^2)=\int_0^t x^2\,dx=\frac{t^3}{3}.
$$
Thus
$$
[S(t^2)]_{B'}=\begin{bmatrix}0\\0\\0\\1/3\end{bmatrix}.
$$

Therefore
$$
[S]_{BB'}=
\begin{bmatrix}
0 & 0 & 0\\
1 & 0 & 0\\
0 & 1/2 & 0\\
0 & 0 & 1/3
\end{bmatrix}.
$$

### Final answer

$$
\boxed{
[S]_{BB'}=
\begin{bmatrix}
0 & 0 & 0\\
1 & 0 & 0\\
0 & 1/2 & 0\\
0 & 0 & 1/3
\end{bmatrix}.
}
$$

---

## Exercise 4.7.14

Let $Q$ be the rotation operator on $\mathbb{R}^2$ through angle $\theta$, and let $R$ be reflection about the $x$-axis.

### (a) Determine $[RQ]_S$.

### (b) Determine the matrix of the operator that rotates by angle $2\theta$.

### Solution

Relative to the standard basis,
$$
[Q]_S=
\begin{bmatrix}
\cos\theta & -\sin\theta\\
\sin\theta & \cos\theta
\end{bmatrix},
\qquad
[R]_S=
\begin{bmatrix}
1 & 0\\
0 & -1
\end{bmatrix}.
$$

### (a) Compute $[RQ]_S$

Because the rightmost map acts first,
$$
[RQ]_S=[R]_S[Q]_S.
$$
Therefore
$$
[RQ]_S
=
\begin{bmatrix}
1 & 0\\
0 & -1
\end{bmatrix}
\begin{bmatrix}
\cos\theta & -\sin\theta\\
\sin\theta & \cos\theta
\end{bmatrix}
=
\begin{bmatrix}
\cos\theta & -\sin\theta\\
-\sin\theta & -\cos\theta
\end{bmatrix}.
$$

### (b) Rotation by $2\theta$

Applying the rotation $Q$ twice rotates by $2\theta$. So
$$
[Q^2]_S=[Q]_S^2.
$$
Compute:
$$
\begin{aligned}
[Q]_S^2
&=
\begin{bmatrix}
\cos\theta & -\sin\theta\\
\sin\theta & \cos\theta
\end{bmatrix}
\begin{bmatrix}
\cos\theta & -\sin\theta\\
\sin\theta & \cos\theta
\end{bmatrix}\\[6pt]
&=
\begin{bmatrix}
\cos^2\theta-\sin^2\theta & -2\sin\theta\cos\theta\\
2\sin\theta\cos\theta & \cos^2\theta-\sin^2\theta
\end{bmatrix}.
\end{aligned}
$$
Using the double-angle identities
$$
\cos 2\theta=\cos^2\theta-\sin^2\theta,
\qquad
\sin 2\theta=2\sin\theta\cos\theta,
$$
we get
$$
[Q^2]_S=
\begin{bmatrix}
\cos 2\theta & -\sin 2\theta\\
\sin 2\theta & \cos 2\theta
\end{bmatrix}.
$$

### Final answer

$$
\boxed{
[RQ]_S=
\begin{bmatrix}
\cos\theta & -\sin\theta\\
-\sin\theta & -\cos\theta
\end{bmatrix},
\qquad
[Q^2]_S=
\begin{bmatrix}
\cos 2\theta & -\sin 2\theta\\
\sin 2\theta & \cos 2\theta
\end{bmatrix}.
}
$$

---

## Exercise 4.7.15

Let $P,Q:U\to V$ be linear transformations, and let $B$ and $B'$ be bases for $U$ and $V$, respectively.

### (a) Explain why
$$
[P+Q]_{BB'}=[P]_{BB'}+[Q]_{BB'}.
$$

### (b) Explain why
$$
[\alpha P]_{BB'}=\alpha [P]_{BB'}.
$$

### Solution

Let
$$
B=\{u_1,\dots,u_n\}.
$$
By definition, the $j$-th column of $[P]_{BB'}$ is $[P(u_j)]_{B'}$, and similarly for $Q$.

### (a) Sum of transformations

The $j$-th column of $[P+Q]_{BB'}$ is
$$
[(P+Q)(u_j)]_{B'}.
$$
Because $P+Q$ is defined pointwise,
$$
(P+Q)(u_j)=P(u_j)+Q(u_j).
$$
Taking coordinates in $B'$,
$$
[(P+Q)(u_j)]_{B'}=[P(u_j)+Q(u_j)]_{B'}=[P(u_j)]_{B'}+[Q(u_j)]_{B'}.
$$
So the $j$-th column of $[P+Q]_{BB'}$ is the sum of the $j$-th columns of $[P]_{BB'}$ and $[Q]_{BB'}$. Since this is true for every column,
$$
\boxed{[P+Q]_{BB'}=[P]_{BB'}+[Q]_{BB'}.}
$$

### (b) Scalar multiple

The $j$-th column of $[\alpha P]_{BB'}$ is
$$
[(\alpha P)(u_j)]_{B'}=[\alpha P(u_j)]_{B'}=\alpha [P(u_j)]_{B'}.
$$
Thus every column of $[\alpha P]_{BB'}$ is $\alpha$ times the corresponding column of $[P]_{BB'}$. Hence
$$
\boxed{[\alpha P]_{BB'}=\alpha [P]_{BB'}.}
$$

---

## Exercise 4.7.16

Let $I$ be the identity operator on an $n$-dimensional space $V$.

### (a) Explain why $[I]_B=I_n$ for every basis $B$.

### (b) Let $B=\{x_i\}_{i=1}^n$ and $B'=\{y_i\}_{i=1}^n$ be two bases, and let $T$ be the operator defined by
$$
T(y_i)=x_i,\qquad i=1,\dots,n.
$$
Explain why
$$
[I]_{BB'}=[T]_B=[T]_{B'}=
\begin{bmatrix}
[x_1]_{B'} & [x_2]_{B'} & \cdots & [x_n]_{B'}
\end{bmatrix}.
$$

### (c) When $V=\mathbb{R}^3$, determine $[I]_{BB'}$ for
$$
B=\left\{
\begin{bmatrix}1\\0\\0\end{bmatrix},
\begin{bmatrix}0\\1\\0\end{bmatrix},
\begin{bmatrix}0\\0\\1\end{bmatrix}
\right\},
\qquad
B'=\left\{
\begin{bmatrix}1\\0\\0\end{bmatrix},
\begin{bmatrix}1\\1\\0\end{bmatrix},
\begin{bmatrix}1\\1\\1\end{bmatrix}
\right\}.
$$

### Solution

### (a) Why $[I]_B=I_n$

Let $B=\{x_1,\dots,x_n\}$. The $j$-th column of $[I]_B$ is
$$
[I(x_j)]_B=[x_j]_B.
$$
But the coordinate vector of the $j$-th basis vector with respect to its own basis is the $j$-th unit vector:
$$
[x_j]_B=e_j.
$$
Therefore the columns of $[I]_B$ are $e_1,e_2,\dots,e_n$, so
$$
[I]_B=I_n.
$$

### (b) Why all three matrices are the same

Write each $x_j$ in the basis $B'$:
$$
x_j=\sum_{i=1}^n \beta_{ij} y_i.
$$
Then
$$
[x_j]_{B'}=
\begin{bmatrix}
\beta_{1j}\\
\beta_{2j}\\
\vdots\\
\beta_{nj}
\end{bmatrix}.
$$

#### First matrix: $[I]_{BB'}$

Its $j$-th column is
$$
[I(x_j)]_{B'}=[x_j]_{B'}.
$$
So
$$
[I]_{BB'}=
\begin{bmatrix}
[x_1]_{B'} & [x_2]_{B'} & \cdots & [x_n]_{B'}
\end{bmatrix}.
$$

#### Second matrix: $[T]_{B'}$

Its $j$-th column is
$$
[T(y_j)]_{B'}=[x_j]_{B'}.
$$
So
$$
[T]_{B'}=
\begin{bmatrix}
[x_1]_{B'} & [x_2]_{B'} & \cdots & [x_n]_{B'}
\end{bmatrix}.
$$

#### Third matrix: $[T]_B$

To get the $j$-th column, we need $[T(x_j)]_B$. Since
$$
x_j=\sum_{i=1}^n \beta_{ij} y_i,
$$
linearity gives
$$
T(x_j)=\sum_{i=1}^n \beta_{ij} T(y_i)=\sum_{i=1}^n \beta_{ij} x_i.
$$
Therefore the coordinates of $T(x_j)$ in the basis $B$ are exactly the same coefficient list:
$$
[T(x_j)]_B=
\begin{bmatrix}
\beta_{1j}\\
\beta_{2j}\\
\vdots\\
\beta_{nj}
\end{bmatrix}
=[x_j]_{B'}.
$$
Hence
$$
[T]_B=
\begin{bmatrix}
[x_1]_{B'} & [x_2]_{B'} & \cdots & [x_n]_{B'}
\end{bmatrix}.
$$

So indeed,
$$
\boxed{
[I]_{BB'}=[T]_B=[T]_{B'}=
\begin{bmatrix}
[x_1]_{B'} & [x_2]_{B'} & \cdots & [x_n]_{B'}
\end{bmatrix}.
}
$$

### (c) Compute $[I]_{BB'}$ for the given bases

Here $B$ is the standard basis, so
$$
x_1=e_1,\qquad x_2=e_2,\qquad x_3=e_3.
$$
We must express these vectors in the basis
$$
B'=\{y_1,y_2,y_3\}
=
\left\{
\begin{bmatrix}1\\0\\0\end{bmatrix},
\begin{bmatrix}1\\1\\0\end{bmatrix},
\begin{bmatrix}1\\1\\1\end{bmatrix}
\right\}.
$$

#### Coordinates of $e_1$

$$
e_1=1y_1+0y_2+0y_3,
\qquad
[e_1]_{B'}=\begin{bmatrix}1\\0\\0\end{bmatrix}.
$$

#### Coordinates of $e_2$

Solve
$$
e_2=a y_1+b y_2+c y_3.
$$
Then
$$
a\begin{bmatrix}1\\0\\0\end{bmatrix}
+b\begin{bmatrix}1\\1\\0\end{bmatrix}
+c\begin{bmatrix}1\\1\\1\end{bmatrix}
=
\begin{bmatrix}0\\1\\0\end{bmatrix},
$$
so
$$
\begin{cases}
a+b+c=0,\\
b+c=1,\\
c=0.
\end{cases}
$$
Hence $c=0$, $b=1$, $a=-1$, and
$$
[e_2]_{B'}=\begin{bmatrix}-1\\1\\0\end{bmatrix}.
$$

#### Coordinates of $e_3$

Solve
$$
e_3=a y_1+b y_2+c y_3.
$$
Then
$$
\begin{cases}
a+b+c=0,\\
b+c=0,\\
c=1.
\end{cases}
$$
So $c=1$, $b=-1$, $a=0$, giving
$$
[e_3]_{B'}=\begin{bmatrix}0\\-1\\1\end{bmatrix}.
$$

Therefore
$$
[I]_{BB'}=
\begin{bmatrix}
1 & -1 & 0\\
0 & 1 & -1\\
0 & 0 & 1
\end{bmatrix}.
$$

### Final answer

$$
\boxed{
[I]_B=I_n,
\qquad
[I]_{BB'}=[T]_B=[T]_{B'}=
\begin{bmatrix}
[x_1]_{B'} & \cdots & [x_n]_{B'}
\end{bmatrix},
\qquad
[I]_{BB'}=
\begin{bmatrix}
1 & -1 & 0\\
0 & 1 & -1\\
0 & 0 & 1
\end{bmatrix}
\text{ in part (c).}
}
$$

---

## Exercise 4.7.17

Let
$$
T(x,y,z)=(2x-y,\,-x+2y-z,\,z-y).
$$

### (a) Determine $T^{-1}(x,y,z)$.

### (b) Determine $[T^{-1}]_S$, where $S$ is the standard basis of $\mathbb{R}^3$.

### Solution

To find $T^{-1}$, rename the input variables:
$$
T(a,b,c)=(2a-b,\,-a+2b-c,\ c-b).
$$
Set
$$
T(a,b,c)=(x,y,z).
$$
Then we must solve
$$
\begin{cases}
x=2a-b,\\
y=-a+2b-c,\\
z=c-b.
\end{cases}
$$

From the third equation,
$$
c=b+z.
$$
Substitute into the second equation:
$$
y=-a+2b-(b+z)=-a+b-z,
$$
so
$$
a=b-y-z.
$$
Substitute that into the first equation:
$$
x=2(b-y-z)-b=b-2y-2z.
$$
Hence
$$
b=x+2y+2z.
$$
Then
$$
a=b-y-z=(x+2y+2z)-y-z=x+y+z,
$$
and
$$
c=b+z=x+2y+3z.
$$

So
$$
T^{-1}(x,y,z)=\bigl(x+y+z,\ x+2y+2z,\ x+2y+3z\bigr).
$$

To check, apply $T$:
$$
\begin{aligned}
2(x+y+z)-(x+2y+2z)&=x,\\
-(x+y+z)+2(x+2y+2z)-(x+2y+3z)&=y,\\
(x+2y+3z)-(x+2y+2z)&=z.
\end{aligned}
$$
So the inverse is correct.

### Part (b): matrix of $T^{-1}$

The columns of $[T^{-1}]_S$ are
$$
[T^{-1}(e_1)]_S,\quad [T^{-1}(e_2)]_S,\quad [T^{-1}(e_3)]_S.
$$
Now
$$
T^{-1}(e_1)=T^{-1}(1,0,0)=(1,1,1),
$$
$$
T^{-1}(e_2)=T^{-1}(0,1,0)=(1,2,2),
$$
$$
T^{-1}(e_3)=T^{-1}(0,0,1)=(1,2,3).
$$
Therefore
$$
[T^{-1}]_S=
\begin{bmatrix}
1 & 1 & 1\\
1 & 2 & 2\\
1 & 2 & 3
\end{bmatrix}.
$$

### Final answer

$$
\boxed{
T^{-1}(x,y,z)=\bigl(x+y+z,\ x+2y+2z,\ x+2y+3z\bigr),
\qquad
[T^{-1}]_S=
\begin{bmatrix}
1 & 1 & 1\\
1 & 2 & 2\\
1 & 2 & 3
\end{bmatrix}.
}
$$

---

## Exercise 4.7.18

Let $T$ be a linear operator on an $n$-dimensional space $V$. Show that the following are equivalent:

1. $T^{-1}$ exists.
2. $T$ is one-to-one.
3. $N(T)=\{0\}$.
4. $T$ is onto.

### Solution

We prove the implications suggested in the hint.

### (1) $\Rightarrow$ (2)

Assume $T^{-1}$ exists. If $T(x)=T(y)$, apply $T^{-1}$ to both sides:
$$
T^{-1}(T(x))=T^{-1}(T(y)).
$$
Thus
$$
x=y.
$$
So $T$ is one-to-one.

---

### (2) $\Rightarrow$ (3)

Assume $T$ is one-to-one. If $u\in N(T)$, then
$$
T(u)=0.
$$
But also
$$
T(0)=0
$$
because $T$ is linear. Since $T$ is one-to-one, the equality $T(u)=T(0)$ implies
$$
u=0.
$$
Hence
$$
N(T)=\{0\}.
$$

---

### (3) $\Rightarrow$ (4)

Assume
$$
N(T)=\{0\}.
$$
Let
$$
B=\{u_1,\dots,u_n\}
$$
be a basis of $V$.

We claim that the set
$$
\{T(u_1),\dots,T(u_n)\}
$$
is linearly independent. Suppose
$$
\alpha_1T(u_1)+\cdots+\alpha_nT(u_n)=0.
$$
By linearity,
$$
T(\alpha_1u_1+\cdots+\alpha_nu_n)=0.
$$
So
$$
\alpha_1u_1+\cdots+\alpha_nu_n\in N(T)=\{0\}.
$$
Therefore
$$
\alpha_1u_1+\cdots+\alpha_nu_n=0.
$$
Since $\{u_1,\dots,u_n\}$ is a basis, it is linearly independent, so all $\alpha_i=0$. This proves that $\{T(u_1),\dots,T(u_n)\}$ is independent.

Now $V$ is $n$-dimensional, and we have $n$ linearly independent vectors in $V$. Therefore they form a basis of $V$. In particular, they span $V$.

Hence every $v\in V$ can be written as
$$
v=\xi_1T(u_1)+\cdots+\xi_nT(u_n)
=
T(\xi_1u_1+\cdots+\xi_nu_n).
$$
So every vector $v$ is $T(x)$ for some $x\in V$. Therefore $T$ is onto.

---

### (4) $\Rightarrow$ (2)

Assume $T$ is onto. Let
$$
B=\{u_1,\dots,u_n\}
$$
be a basis of $V$. Since $T$ is onto, for each $u_i$ there exists some $v_i\in V$ such that
$$
T(v_i)=u_i.
$$

We claim that $\{v_1,\dots,v_n\}$ is linearly independent. Suppose
$$
\alpha_1v_1+\cdots+\alpha_nv_n=0.
$$
Apply $T$:
$$
0=T(0)=T(\alpha_1v_1+\cdots+\alpha_nv_n)=\alpha_1u_1+\cdots+\alpha_nu_n.
$$
Since $\{u_1,\dots,u_n\}$ is independent, all $\alpha_i=0$. Thus $\{v_1,\dots,v_n\}$ is independent. With $n$ independent vectors in an $n$-dimensional space, it is a basis.

Now suppose $T(x)=T(y)$. Then
$$
T(x-y)=0.
$$
Because $\{v_1,\dots,v_n\}$ is a basis, write
$$
x-y=\xi_1v_1+\cdots+\xi_nv_n.
$$
Apply $T$:
$$
0=T(x-y)=\xi_1u_1+\cdots+\xi_nu_n.
$$
Again, since $\{u_1,\dots,u_n\}$ is independent, all $\xi_i=0$. Thus $x-y=0$, so $x=y$.

Therefore $T$ is one-to-one.

---

### (2) and (4) $\Rightarrow$ (1)

Assume $T$ is both one-to-one and onto. Then for every $y\in V$, there exists a **unique** $x\in V$ such that
$$
T(x)=y.
$$
This allows us to define a function
$$
T^{-1}:V\to V
$$
by saying
$$
T^{-1}(y)=x
\quad\text{where }T(x)=y.
$$

We now check linearity. Let $y_1,y_2\in V$, and let
$$
x_1=T^{-1}(y_1),\qquad x_2=T^{-1}(y_2).
$$
Then
$$
T(x_1)=y_1,\qquad T(x_2)=y_2.
$$
For scalar $\alpha$,
$$
T(\alpha x_1+x_2)=\alpha T(x_1)+T(x_2)=\alpha y_1+y_2.
$$
Because preimages are unique, the vector $\alpha x_1+x_2$ must equal $T^{-1}(\alpha y_1+y_2)$. Hence
$$
T^{-1}(\alpha y_1+y_2)=\alpha T^{-1}(y_1)+T^{-1}(y_2).
$$
So $T^{-1}$ is linear.

Finally, by construction,
$$
TT^{-1}=I
\qquad\text{and}\qquad
T^{-1}T=I.
$$
Therefore $T^{-1}$ exists.

---

### Conclusion

All four statements are equivalent:

$$
\boxed{
T^{-1}\text{ exists}
\iff
T\text{ is one-to-one}
\iff
N(T)=\{0\}
\iff
T\text{ is onto}.
}
$$

---

## Exercise 4.7.19

Let $V$ be an $n$-dimensional space with basis $B=\{u_i\}_{i=1}^n$.

### (a) Prove that $\{x_1,\dots,x_r\}\subseteq V$ is linearly independent if and only if
$$
\{[x_1]_B,\dots,[x_r]_B\}\subseteq \mathbb{R}^{n\times 1}
$$
is linearly independent.

### (b) If $T$ is a linear operator on $V$, explain why the vectors corresponding to the basic columns of $[T]_B$ form a basis for $R(T)$.

### Solution

## Part (a)

We prove both directions.

### If $\{x_1,\dots,x_r\}$ is linearly independent, then $\{[x_1]_B,\dots,[x_r]_B\}$ is linearly independent.

Assume
$$
\alpha_1[x_1]_B+\cdots+\alpha_r[x_r]_B=0.
$$
Because coordinate-taking is linear,
$$
\alpha_1[x_1]_B+\cdots+\alpha_r[x_r]_B
=
[\alpha_1x_1+\cdots+\alpha_rx_r]_B.
$$
So
$$
[\alpha_1x_1+\cdots+\alpha_rx_r]_B=0=[0]_B.
$$
A vector has zero coordinate vector only if the vector itself is zero. Hence
$$
\alpha_1x_1+\cdots+\alpha_rx_r=0.
$$
Since $\{x_1,\dots,x_r\}$ is linearly independent, all $\alpha_i=0$. Therefore the coordinate vectors are linearly independent.

### Conversely, if $\{[x_1]_B,\dots,[x_r]_B\}$ is linearly independent, then $\{x_1,\dots,x_r\}$ is linearly independent.

Assume
$$
\alpha_1x_1+\cdots+\alpha_rx_r=0.
$$
Take coordinates in the basis $B$:
$$
[\alpha_1x_1+\cdots+\alpha_rx_r]_B=[0]_B=0.
$$
By linearity of coordinates,
$$
\alpha_1[x_1]_B+\cdots+\alpha_r[x_r]_B=0.
$$
Since the coordinate vectors are linearly independent, all $\alpha_i=0$. Hence $\{x_1,\dots,x_r\}$ is linearly independent.

So we have proved
$$
\boxed{
\{x_1,\dots,x_r\}\text{ is linearly independent }
\iff
\{[x_1]_B,\dots,[x_r]_B\}\text{ is linearly independent.}
}
$$

## Part (b)

We want to show that the vectors corresponding to the basic columns of $[T]_B$ form a basis for the range $R(T)$.

Let
$$
B=\{u_1,\dots,u_n\}.
$$
Since every $x\in V$ has the form
$$
x=\xi_1u_1+\cdots+\xi_nu_n,
$$
linearity gives
$$
T(x)=\xi_1T(u_1)+\cdots+\xi_nT(u_n).
$$
Therefore
$$
R(T)=\operatorname{span}\{T(u_1),\dots,T(u_n)\}.
$$
So the range is spanned by the images of the basis vectors.

Now recall that the columns of $[T]_B$ are exactly
$$
[T(u_1)]_B,\ [T(u_2)]_B,\ \dots,\ [T(u_n)]_B.
$$
Suppose the basic columns occur in positions $b_1,\dots,b_r$. Then the basic columns form a basis for the column space of $[T]_B$. In particular:

1. The columns
   $$
   [T(u_{b_1})]_B,\dots,[T(u_{b_r})]_B
   $$
   are linearly independent.

2. Every other column $[T(u_j)]_B$ is a linear combination of those basic columns.

By part (a), linear independence of those coordinate columns implies linear independence of the actual vectors
$$
T(u_{b_1}),\dots,T(u_{b_r}).
$$
Also, if
$$
[T(u_j)]_B
=
c_1[T(u_{b_1})]_B+\cdots+c_r[T(u_{b_r})]_B,
$$
then again by part (a) (or by the uniqueness of coordinates),
$$
T(u_j)=c_1T(u_{b_1})+\cdots+c_rT(u_{b_r}).
$$
So every $T(u_j)$ lies in the span of
$$
T(u_{b_1}),\dots,T(u_{b_r}).
$$
Since the whole range is spanned by all $T(u_j)$, it follows that
$$
R(T)=\operatorname{span}\{T(u_{b_1}),\dots,T(u_{b_r})\}.
$$
And we already know these vectors are linearly independent. Therefore they form a basis for the range.

### Final answer

$$
\boxed{
\{T(u_{b_1}),\dots,T(u_{b_r})\}\text{ is a basis for }R(T).
}
$$

---

## Endnote

The main conceptual takeaway from Section 4.7 is this:

- abstract linear maps become concrete once bases are chosen;
- their action is encoded by coordinate matrices;
- composition becomes matrix multiplication;
- invertibility becomes matrix invertibility.

Those four ideas are exactly what the exercises in this section are training.
