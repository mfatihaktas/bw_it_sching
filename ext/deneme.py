import cvxpy as cvx
import numpy as np
'''
# Make random input repeatable. 
np.random.seed(0) 

# Matrix size parameters.
n = 20
m = 10
p = 5

# Generate random problem data.
tmp = np.mat(np.random.rand(n, 1))
A = np.mat(np.random.randn(m, n))
b = A*tmp
F = np.mat(np.random.randn(p, n))
g = F*tmp + np.mat(np.random.rand(p, 1))

# Entropy maximization.
x = cvx.Variable(n)
obj = cvx.Maximize(cvx.sum_entries(cvx.entr(x)))
constraints = [A*x == b,
               F*x <= g ]
prob = cvx.Problem(obj, constraints)
prob.solve(solver=cvx.CVXOPT, verbose=True)

'''
x = cvx.Variable(name='x')
y = cvx.Variable(name='y')
v = cvx.Variable(2,1, name='v')

prob = cvx.Problem(cvx.Minimize(x + y), 
                   [cvx.vstack(x, y) > v] +\
                   [v > cvx.vstack(2, 3)] )
prob.solve(solver=cvx.CVXOPT, verbose=True)

# Print result.
print "\nThe optimal value is:", prob.value
print '\nThe optimal solution is:'
print x.value