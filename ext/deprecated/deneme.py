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
m = cvx.Variable(2, 2, name='m')

prob = cvx.Problem(cvx.Minimize(cvx.trace(m)),
                   [m > 1] )
prob.solve(solver=cvx.CVXOPT, verbose=True)

# Print result.
print "prob.value= %s" % prob.value
print 'm.value= \n%s' % m.value
print 'm[:, 0].value= \n%s' % m[:, 0].value
m_ = m[:, 0].value
print 'm_[0]= \n%s' % m_[0]
print 'float(m_[0])= \n%s' % float(m_[0])